import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import Settings
from .database import get_db
from .models import AuthSession, PlayerProfile, User


def validate_telegram_init_data(init_data: str, bot_token: str, max_age_seconds: int) -> dict:
    fields = dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=True))
    supplied_hash = fields.pop("hash", None)
    if not supplied_hash or "auth_date" not in fields or "user" not in fields:
        raise ValueError("Telegram initData is incomplete")

    check_string = "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected_hash = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_hash, supplied_hash):
        raise ValueError("Telegram initData signature is invalid")

    try:
        auth_timestamp = int(fields["auth_date"])
        telegram_user = json.loads(fields["user"])
        telegram_id = int(telegram_user["id"])
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
        raise ValueError("Telegram initData contains invalid user data") from error

    age = datetime.now(timezone.utc).timestamp() - auth_timestamp
    if age < -30 or age > max_age_seconds:
        raise ValueError("Telegram initData has expired")
    if telegram_id <= 0:
        raise ValueError("Telegram user id is invalid")
    return telegram_user


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def issue_session(request: Request, db: Session, user: User) -> None:
    settings: Settings = request.app.state.settings
    token = secrets.token_urlsafe(32)
    db.add(
        AuthSession(
            token_hash=token_digest(token),
            user_id=user.id,
            expires_at=datetime.now(timezone.utc).replace(microsecond=0)
            + timedelta(seconds=settings.session_ttl_seconds),
        )
    )
    request.state.session_token = token


def get_current_player(
    request: Request,
    db: Session = Depends(get_db),
) -> tuple[User, PlayerProfile]:
    settings: Settings = request.app.state.settings
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Debes iniciar sesión.")
    auth_session = db.scalar(
        select(AuthSession).where(AuthSession.token_hash == token_digest(token))
    )
    now = datetime.now(timezone.utc)
    if auth_session is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "La sesión no es válida.")
    expires_at = auth_session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now:
        db.delete(auth_session)
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "La sesión expiró.")

    user = db.get(User, auth_session.user_id)
    profile = db.get(PlayerProfile, auth_session.user_id)
    if user is None or profile is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "El perfil no está disponible.")
    return user, profile
