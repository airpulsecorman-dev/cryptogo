import time
from datetime import datetime

import redis
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AuthSession, PlayerProfile, User
from ..schemas import DevelopmentAuthRequest, TelegramAuthRequest
from ..security import get_current_player, issue_session, token_digest, validate_telegram_init_data

router = APIRouter(prefix="/auth", tags=["authentication"])


def _rate_limit(request: Request, key: str, limit: int, window_seconds: int) -> None:
    if request.app.state.settings.app_env == "test":
        return
    client = request.app.state.redis
    bucket = int(time.time()) // window_seconds
    redis_key = f"rate:{key}:{bucket}"
    try:
        count = client.incr(redis_key)
        if count == 1:
            client.expire(redis_key, window_seconds + 1)
    except redis.RedisError as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "El control de solicitudes no está disponible.") from error
    if count > limit:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Demasiados intentos. Espera antes de volver a probar.")


def _find_or_create_user(db: Session, telegram_user: dict) -> User:
    telegram_id = int(telegram_user["id"])
    user = db.scalar(select(User).where(User.telegram_id == telegram_id).with_for_update())
    if user is None:
        user = User(
            telegram_id=telegram_id,
            first_name=str(telegram_user.get("first_name") or "Jugador")[:128],
            username=(str(telegram_user["username"])[:64] if telegram_user.get("username") else None),
        )
        db.add(user)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            user = db.scalar(select(User).where(User.telegram_id == telegram_id).with_for_update())
            if user is None:
                raise
    else:
        user.first_name = str(telegram_user.get("first_name") or user.first_name)[:128]
        user.username = str(telegram_user["username"])[:64] if telegram_user.get("username") else None
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
    _rate_limit(request, f"auth:{request.client.host if request.client else 'unknown'}", 10, 600)
    settings = request.app.state.settings
    if not settings.telegram_bot_token:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "La autenticación de Telegram no está configurada.")
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
        {"id": body.telegram_id, "first_name": body.first_name, "username": body.username},
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
