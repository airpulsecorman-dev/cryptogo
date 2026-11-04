import secrets
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

import redis
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AuthChallenge, AuthSession, PlayerProfile, User, WalletIdentity
from ..schemas import (
    DevelopmentAuthRequest,
    EvmChallengeRequest,
    EvmVerifyRequest,
    TelegramAuthRequest,
    TonWalletAuthRequest,
)
from ..security import (
    get_current_player,
    issue_session,
    token_digest,
    validate_telegram_init_data,
)
from ..wallet_auth import (
    canonical_evm_address,
    domain_from_origin,
    recover_evm_signer,
    verify_ton_proof,
)

router = APIRouter(prefix="/auth", tags=["authentication"])


def _rate_limit(request: Request, key: str, limit: int, window_seconds: int) -> None:
    if request.app.state.settings.app_env == "test":
        return
    client = request.app.state.redis
    bucket = int(time.time()) // window_seconds
    redis_key = f"rate:{key}:{bucket}"
    try:
        count = client.eval(
            "local count = redis.call('INCR', KEYS[1]); "
            "if count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]); end; "
            "return count",
            1,
            redis_key,
            window_seconds + 1,
        )
    except redis.RedisError as error:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "El control de solicitudes no está disponible.",
        ) from error
    if count > limit:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Demasiados intentos. Espera antes de volver a probar.",
        )


def _find_or_create_user(db: Session, telegram_user: dict) -> User:
    telegram_id = int(telegram_user["id"])
    user = db.scalar(
        select(User).where(User.telegram_id == telegram_id).with_for_update()
    )
    if user is None:
        user = User(
            telegram_id=telegram_id,
            first_name=str(telegram_user.get("first_name") or "Jugador")[:128],
            username=(
                str(telegram_user["username"])[:64]
                if telegram_user.get("username")
                else None
            ),
        )
        db.add(user)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            user = db.scalar(
                select(User).where(User.telegram_id == telegram_id).with_for_update()
            )
            if user is None:
                raise
    else:
        user.first_name = str(telegram_user.get("first_name") or user.first_name)[:128]
        user.username = (
            str(telegram_user["username"])[:64]
            if telegram_user.get("username")
            else None
        )
    if db.get(PlayerProfile, user.id) is None:
        db.add(PlayerProfile(user_id=user.id))
    db.flush()
    return user


def _authenticate(
    request: Request,
    response: Response,
    db: Session,
    telegram_user: dict,
) -> dict:
    user = _find_or_create_user(db, telegram_user)
    issue_session(request, db, user)
    db.commit()
    settings = request.app.state.settings
    response.set_cookie(
        settings.session_cookie_name,
        request.state.session_token,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        path="/",
    )
    profile = db.get(PlayerProfile, user.id)
    return {
        "id": str(user.id),
        "telegram_id": user.telegram_id,
        "first_name": user.first_name,
        "username": user.username,
        "points": profile.points,
        "total_xp": profile.total_xp,
        "level": _level_for_xp(profile.total_xp),
        "xp_into_level": _xp_into_level(profile.total_xp),
        "xp_for_next_level": _xp_for_next_level(profile.total_xp),
        "collected_count": profile.collected_count,
        "registered_at": user.created_at,
    }


def _request_origin(request: Request) -> tuple[str, str]:
    origin = request.headers.get("origin")
    if not origin or origin not in request.app.state.settings.allowed_origins:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Origen de autenticación no permitido."
        )
    parsed = urlsplit(origin)
    if (
        not parsed.hostname
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Origen de autenticación no válido."
        )
    return origin, domain_from_origin(origin)


def _expire_wallet_challenges(db: Session, now: datetime) -> None:
    db.query(AuthChallenge).filter(AuthChallenge.expires_at <= now).delete(
        synchronize_session=False
    )


def _create_wallet_challenge(
    db: Session,
    *,
    provider: str,
    address: str | None,
    network: str | None,
    domain: str,
    uri: str,
    message: str | None,
    nonce: str,
    expires_at: datetime,
) -> None:
    now = datetime.now(timezone.utc)
    _expire_wallet_challenges(db, now)
    db.add(
        AuthChallenge(
            nonce=nonce,
            provider=provider,
            address=address,
            network=network,
            domain=domain,
            uri=uri,
            message=message,
            expires_at=expires_at,
        )
    )
    db.commit()


def _consume_wallet_challenge(
    db: Session, *, nonce: str, provider: str, now: datetime
) -> AuthChallenge:
    challenge = db.scalar(
        select(AuthChallenge)
        .where(
            AuthChallenge.nonce == nonce,
            AuthChallenge.provider == provider,
        )
        .with_for_update()
    )
    if challenge is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "El desafío no es válido.")
    expires_at = challenge.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now:
        db.delete(challenge)
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "El desafío expiró.")
    return challenge


def _wallet_player_response(user: User, profile: PlayerProfile) -> dict:
    return {
        "id": str(user.id),
        "telegram_id": user.telegram_id,
        "first_name": user.first_name,
        "username": user.username,
        "points": profile.points,
        "total_xp": profile.total_xp,
        "level": _level_for_xp(profile.total_xp),
        "xp_into_level": _xp_into_level(profile.total_xp),
        "xp_for_next_level": _xp_for_next_level(profile.total_xp),
        "collected_count": profile.collected_count,
        "registered_at": user.created_at,
    }


def _authenticate_wallet(
    request: Request,
    response: Response,
    db: Session,
    *,
    provider: str,
    network: str,
    address: str,
) -> dict:
    identity = db.scalar(
        select(WalletIdentity)
        .where(
            WalletIdentity.provider == provider,
            WalletIdentity.network == network,
            WalletIdentity.address == address,
        )
        .with_for_update()
    )
    if identity is None:
        display_address = f"{address[:8]}…{address[-6:]}"
        user = User(
            telegram_id=None,
            first_name=f"Jugador {display_address}"[:128],
            username=None,
        )
        db.add(user)
        db.flush()
        identity = WalletIdentity(
            user_id=user.id,
            provider=provider,
            network=network,
            address=address,
        )
        db.add_all([identity, PlayerProfile(user_id=user.id)])
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            identity = db.scalar(
                select(WalletIdentity).where(
                    WalletIdentity.provider == provider,
                    WalletIdentity.network == network,
                    WalletIdentity.address == address,
                )
            )
            if identity is None:
                raise
            user = db.get(User, identity.user_id)
    else:
        user = db.get(User, identity.user_id)

    if user is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "La cuenta no está disponible."
        )
    profile = db.get(PlayerProfile, user.id)
    if profile is None:
        profile = PlayerProfile(user_id=user.id)
        db.add(profile)
        db.flush()

    issue_session(request, db, user)
    db.commit()
    settings = request.app.state.settings
    response.set_cookie(
        settings.session_cookie_name,
        request.state.session_token,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        path="/",
    )
    return _wallet_player_response(user, profile)


def _level_for_xp(total_xp: int) -> int:
    level = 1
    while total_xp >= level * level * 500:
        level += 1
    return level


def _xp_into_level(total_xp: int) -> int:
    level = _level_for_xp(total_xp)
    return total_xp - (level - 1) ** 2 * 500


def _xp_for_next_level(total_xp: int) -> int:
    level = _level_for_xp(total_xp)
    return (level * level - (level - 1) ** 2) * 500


@router.post("/telegram")
def authenticate_telegram(
    body: TelegramAuthRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    _rate_limit(
        request, f"auth:{request.client.host if request.client else 'unknown'}", 10, 600
    )
    settings = request.app.state.settings
    if not settings.telegram_bot_token:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "La autenticación de Telegram no está configurada.",
        )
    try:
        telegram_user = validate_telegram_init_data(
            body.init_data,
            settings.telegram_bot_token,
            settings.telegram_auth_max_age_seconds,
        )
        return _authenticate(request, response, db, telegram_user)
    except ValueError as error:
        db.rollback()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(error)) from error


@router.post("/evm/challenge")
def create_evm_challenge(
    body: EvmChallengeRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    _rate_limit(
        request,
        f"wallet-challenge:{request.client.host if request.client else 'unknown'}",
        10,
        600,
    )
    origin, domain = _request_origin(request)
    try:
        address = canonical_evm_address(body.address)
    except ValueError as error:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)
        ) from error

    now = datetime.now(timezone.utc).replace(microsecond=0)
    expires_at = now + timedelta(
        seconds=request.app.state.settings.wallet_auth_max_age_seconds
    )
    nonce = secrets.token_hex(32)
    issued_at = now.isoformat().replace("+00:00", "Z")
    expiration_time = expires_at.isoformat().replace("+00:00", "Z")
    message = (
        f"{domain} wants you to sign in with your Ethereum account:\n"
        f"{address}\n\n"
        "Sign in to Crypto Go. This request will not trigger a blockchain transaction.\n\n"
        f"URI: {origin}\n"
        "Version: 1\n"
        f"Chain ID: {body.chain_id}\n"
        f"Nonce: {nonce}\n"
        f"Issued At: {issued_at}\n"
        f"Expiration Time: {expiration_time}"
    )
    _create_wallet_challenge(
        db,
        provider="evm",
        address=address.lower(),
        network=str(body.chain_id),
        domain=domain,
        uri=origin,
        message=message,
        nonce=nonce,
        expires_at=expires_at,
    )
    return {"nonce": nonce, "message": message}


@router.post("/evm/verify")
def authenticate_evm_wallet(
    body: EvmVerifyRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    _rate_limit(
        request,
        f"wallet-verify:{request.client.host if request.client else 'unknown'}",
        20,
        600,
    )
    origin, _domain = _request_origin(request)
    try:
        address = canonical_evm_address(body.address)
    except ValueError as error:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "La dirección EVM no es válida."
        ) from error
    challenge = _consume_wallet_challenge(
        db,
        nonce=body.nonce,
        provider="evm",
        now=datetime.now(timezone.utc),
    )
    if (
        challenge.address != address.lower()
        or challenge.network != str(body.chain_id)
        or challenge.uri != origin
        or challenge.message is None
    ):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "El desafío EVM no coincide."
        )
    try:
        signer = canonical_evm_address(
            recover_evm_signer(challenge.message, body.signature)
        )
    except (ValueError, TypeError) as error:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "La firma EVM no es válida."
        ) from error
    if signer.lower() != address.lower():
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "La firma EVM no corresponde a la billetera.",
        )

    db.delete(challenge)
    db.commit()
    return _authenticate_wallet(
        request,
        response,
        db,
        provider="evm",
        network="evm",
        address=address.lower(),
    )


@router.post("/ton/challenge")
def create_ton_challenge(
    request: Request,
    db: Session = Depends(get_db),
):
    _rate_limit(
        request,
        f"wallet-challenge:{request.client.host if request.client else 'unknown'}",
        10,
        600,
    )
    origin, domain = _request_origin(request)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    expires_at = now + timedelta(
        seconds=request.app.state.settings.wallet_auth_max_age_seconds
    )
    payload = secrets.token_urlsafe(32)
    _create_wallet_challenge(
        db,
        provider="ton",
        address=None,
        network=None,
        domain=domain,
        uri=origin,
        message=None,
        nonce=payload,
        expires_at=expires_at,
    )
    return {"payload": payload}


@router.post("/ton/verify")
def authenticate_ton_wallet(
    body: TonWalletAuthRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    _rate_limit(
        request,
        f"wallet-verify:{request.client.host if request.client else 'unknown'}",
        20,
        600,
    )
    origin, domain = _request_origin(request)
    challenge = _consume_wallet_challenge(
        db,
        nonce=body.proof.payload,
        provider="ton",
        now=datetime.now(timezone.utc),
    )
    if challenge.uri != origin or challenge.domain != domain:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "El desafío TON no coincide."
        )
    try:
        address, network = verify_ton_proof(
            settings=request.app.state.settings,
            address=body.address,
            network=body.network,
            claimed_public_key=body.public_key,
            proof=body.proof,
            expected_domain=challenge.domain,
            expected_payload=challenge.nonce,
        )
    except ValueError as error:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(error)) from error
    except RuntimeError as error:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, str(error)
        ) from error

    db.delete(challenge)
    db.commit()
    return _authenticate_wallet(
        request,
        response,
        db,
        provider="ton",
        network=network,
        address=address,
    )


@router.post("/dev")
def authenticate_development(
    body: DevelopmentAuthRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    settings = request.app.state.settings
    if settings.app_env != "development" or not settings.dev_auth_enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ruta no disponible.")
    return _authenticate(
        request,
        response,
        db,
        {
            "id": body.telegram_id,
            "first_name": body.first_name,
            "username": body.username,
        },
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    player=Depends(get_current_player),
    db: Session = Depends(get_db),
):
    token = request.cookies.get(request.app.state.settings.session_cookie_name)
    if token:
        session = db.get(AuthSession, token_digest(token))
        if session is not None:
            db.delete(session)
            db.commit()
    response.delete_cookie(
        request.app.state.settings.session_cookie_name,
        path="/",
        secure=request.app.state.settings.session_cookie_secure,
        httponly=True,
        samesite=request.app.state.settings.session_cookie_samesite,
    )
