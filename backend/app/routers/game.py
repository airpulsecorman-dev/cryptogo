import hashlib
import json
from datetime import timedelta, timezone
from uuid import UUID

import redis
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from ..database import get_db
from ..geo import haversine_meters, nearby_rows, point_is_in_enabled_zone
from ..models import (
    AntiCheatEvent,
    Collection,
    Collectible,
    IdempotencyRecord,
    PlayerProfile,
    PointTransaction,
    SpawnInstance,
    User,
    XPTransaction,
    utcnow,
)
from ..schemas import CollectRequest, CollectResponse, InventoryResponse, PlayerResponse
from ..security import get_current_player
from .auth import _level_for_xp, _xp_for_next_level, _xp_into_level

router = APIRouter(tags=["game"])


def _player_payload(user: User, profile: PlayerProfile) -> dict:
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


def _log_anomaly(
    db: Session, user_id: UUID, spawn_id: UUID | None, reason: str
) -> None:
    db.add(AntiCheatEvent(user_id=user_id, spawn_instance_id=spawn_id, reason=reason))
    db.commit()


def _collect_rate_limit(request: Request, user_id: UUID) -> None:
    if request.app.state.settings.app_env == "test":
        return
    try:
        key = f"rate:collect:{user_id}:{int(utcnow().timestamp()) // 60}"
        count = request.app.state.redis.eval(
            "local count = redis.call('INCR', KEYS[1]); "
            "if count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]); end; "
            "return count",
            1,
            key,
            61,
        )
    except redis.RedisError as error:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "El control de solicitudes no está disponible.",
        ) from error
    if count > 20:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Se alcanzó el límite temporal de recolecciones.",
        )


def _distance(
    db: Session, latitude: float, longitude: float, spawn: SpawnInstance
) -> float:
    if db.bind.dialect.name == "postgresql":
        return float(
            db.execute(
                text(
                    "SELECT ST_Distance("
                    "ST_SetSRID(ST_MakePoint(:spawn_longitude, :spawn_latitude), 4326)::geography, "
                    "ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326)::geography)"
                ),
                {
                    "spawn_longitude": spawn.longitude,
                    "spawn_latitude": spawn.latitude,
                    "longitude": longitude,
                    "latitude": latitude,
                },
            ).scalar_one()
        )
    return haversine_meters(latitude, longitude, spawn.latitude, spawn.longitude)


@router.get("/players/me", response_model=PlayerResponse)
def get_profile(player=Depends(get_current_player)):
    user, profile = player
    return _player_payload(user, profile)


@router.get("/collectibles/nearby")
def get_nearby_collectibles(
    latitude: float = Query(ge=-90, le=90),
    longitude: float = Query(ge=-180, le=180),
    radius_meters: int = Query(default=1_500, ge=1, le=5_000),
    player=Depends(get_current_player),
    db: Session = Depends(get_db),
):
    if not point_is_in_enabled_zone(db, latitude, longitude):
        return {
            "items": [],
            "message": "No hay una zona de juego habilitada en esta ubicación.",
        }
    now = utcnow()
    rows = nearby_rows(db, latitude, longitude, radius_meters, now)
    items = [
        {
            "id": row["id"],
            "ticker": row["ticker"],
            "name": row["name"],
            "symbol": row["symbol"],
            "rarity": row["rarity"],
            "latitude": row["latitude"],
            "longitude": row["longitude"],
            "distance_meters": round(float(row["distance_meters"]), 1),
            "collection_radius_meters": row["collection_radius_meters"],
            "expires_at": row["expires_at"],
        }
        for row in rows
    ]
    return {"items": items, "message": None}


@router.get("/zones/nearby")
def get_nearby_zones(
    latitude: float = Query(ge=-90, le=90),
    longitude: float = Query(ge=-180, le=180),
    player=Depends(get_current_player),
    db: Session = Depends(get_db),
):
    from ..models import Zone

    zones = db.query(Zone).filter(Zone.enabled.is_(True)).all()
    return {
        "items": [
            {
                "id": zone.id,
                "name": zone.name,
                "boundary": json.loads(zone.boundary_geojson),
            }
            for zone in zones
            if point_is_in_enabled_zone(db, latitude, longitude, zone.id)
        ]
    }


@router.post("/collectibles/collect", response_model=CollectResponse)
def collect(
    body: CollectRequest,
    request: Request,
    player=Depends(get_current_player),
    db: Session = Depends(get_db),
    idempotency_key: str = Header(
        min_length=16, max_length=128, alias="Idempotency-Key"
    ),
):
    user, _profile = player
    _collect_rate_limit(request, user.id)

    request_hash = hashlib.sha256(body.model_dump_json().encode()).hexdigest()
    existing = db.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.user_id == user.id,
            IdempotencyRecord.key == idempotency_key,
        )
    )
    if existing is not None:
        if existing.request_hash != request_hash:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "La clave de idempotencia ya se usó con otra solicitud.",
            )
        return existing.response_body

    now = utcnow()
    age = now - body.client_timestamp.astimezone(timezone.utc)
    if age < timedelta(seconds=-15) or age > timedelta(
        seconds=request.app.state.settings.max_client_location_age_seconds
    ):
        _log_anomaly(db, user.id, body.spawn_instance_id, "stale_or_future_location")
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "La ubicación es demasiado antigua."
        )
    if body.accuracy_meters > request.app.state.settings.max_location_accuracy_meters:
        _log_anomaly(db, user.id, body.spawn_instance_id, "low_location_accuracy")
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "La ubicación no tiene precisión suficiente.",
        )

    spawn = db.scalar(
        select(SpawnInstance)
        .where(SpawnInstance.id == body.spawn_instance_id)
        .with_for_update()
    )
    if spawn is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El objeto no existe.")

    # Re-check after acquiring the row lock so simultaneous retries return the
    # original response instead of applying the reward twice.
    existing = db.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.user_id == user.id,
            IdempotencyRecord.key == idempotency_key,
        )
    )
    if existing is not None:
        if existing.request_hash != request_hash:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "La clave de idempotencia ya se usó con otra solicitud.",
            )
        return existing.response_body

    if spawn.state != "available":
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Este objeto ya no está disponible."
        )
    expires_at = spawn.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now:
        spawn.state = "expired"
        db.commit()
        raise HTTPException(status.HTTP_410_GONE, "Este objeto expiró.")

    if not point_is_in_enabled_zone(
        db, spawn.latitude, spawn.longitude, spawn.zone_id
    ) or not point_is_in_enabled_zone(db, body.latitude, body.longitude, spawn.zone_id):
        _log_anomaly(db, user.id, spawn.id, "outside_enabled_zone")
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "La ubicación está fuera de una zona habilitada."
        )

    distance = _distance(db, body.latitude, body.longitude, spawn)
    if distance > min(
        spawn.collection_radius_meters, request.app.state.settings.collect_radius_meters
    ):
        _log_anomaly(db, user.id, spawn.id, "outside_collection_radius")
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Debes acercarte más al objeto para recogerlo."
        )

    collectible = db.get(Collectible, spawn.collectible_id)
    if collectible is None or not collectible.enabled:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Este objeto ya no está disponible."
        )

    profile = db.scalar(
        select(PlayerProfile)
        .where(PlayerProfile.user_id == user.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if profile is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "El perfil del jugador no está disponible."
        )
    collection = Collection(
        user_id=user.id,
        spawn_instance_id=spawn.id,
        collectible_id=collectible.id,
    )
    db.add(collection)
    spawn.state = "collected"
    profile.points += collectible.points_reward
    profile.total_xp += collectible.xp_reward
    profile.collected_count += 1
    profile.updated_at = now
    db.flush()
    db.add(
        PointTransaction(
            user_id=user.id,
            collection_id=collection.id,
            amount=collectible.points_reward,
        )
    )
    db.add(
        XPTransaction(
            user_id=user.id,
            collection_id=collection.id,
            amount=collectible.xp_reward,
        )
    )
    result = {
        "success": True,
        "collection_id": str(collection.id),
        "collectible": {
            "ticker": collectible.ticker,
            "name": collectible.name,
            "rarity": collectible.rarity,
        },
        "rewards": {"points": collectible.points_reward, "xp": collectible.xp_reward},
        "player": _player_payload(user, profile),
        "message": f"{collectible.name} añadido a tu colección.",
    }
    db.add(
        IdempotencyRecord(
            user_id=user.id,
            key=idempotency_key,
            request_hash=request_hash,
            response_body=jsonable_encoder(result),
        )
    )
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        retry = db.scalar(
            select(IdempotencyRecord).where(
                IdempotencyRecord.user_id == user.id,
                IdempotencyRecord.key == idempotency_key,
            )
        )
        if retry is not None and retry.request_hash == request_hash:
            return retry.response_body
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Este objeto ya fue recogido."
        ) from error
    except SQLAlchemyError:
        db.rollback()
        raise
    return result


@router.get("/inventory", response_model=InventoryResponse)
def get_inventory(
    player=Depends(get_current_player),
    db: Session = Depends(get_db),
):
    user, profile = player
    item_rows = (
        db.query(
            Collectible.ticker,
            Collectible.name,
            Collectible.symbol,
            Collectible.rarity,
            func.count(Collection.id).label("count"),
        )
        .join(Collection, Collection.collectible_id == Collectible.id)
        .filter(Collection.user_id == user.id)
        .group_by(Collectible.id)
        .order_by(Collectible.ticker)
        .all()
    )
    history_rows = (
        db.query(Collection, Collectible, PointTransaction, XPTransaction)
        .join(Collectible, Collectible.id == Collection.collectible_id)
        .join(PointTransaction, PointTransaction.collection_id == Collection.id)
        .join(XPTransaction, XPTransaction.collection_id == Collection.id)
        .filter(Collection.user_id == user.id)
        .order_by(Collection.collected_at.desc())
        .limit(50)
        .all()
    )
    return {
        "items": [dict(row._mapping) for row in item_rows],
        "history": [
            {
                "collection_id": collection.id,
                "ticker": collectible.ticker,
                "name": collectible.name,
                "collected_at": collection.collected_at,
                "points": point_tx.amount,
                "xp": xp_tx.amount,
            }
            for collection, collectible, point_tx, xp_tx in history_rows
        ],
        "total_collected": profile.collected_count,
    }


@router.get("/missions")
def get_missions(player=Depends(get_current_player)):
    return {"items": [], "message": "No hay misiones habilitadas todavía."}


@router.get("/leaderboard")
def get_leaderboard(
    player=Depends(get_current_player),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=100),
):
    user, _profile = player
    rows = (
        db.query(PlayerProfile, User)
        .join(User, User.id == PlayerProfile.user_id)
        .order_by(PlayerProfile.points.desc(), PlayerProfile.updated_at, User.id)
        .limit(limit)
        .all()
    )
    return {
        "items": [
            {
                "rank": rank,
                "first_name": candidate.first_name,
                "points": candidate_profile.points,
                "level": _level_for_xp(candidate_profile.total_xp),
                "is_current_player": candidate.id == user.id,
            }
            for rank, (candidate_profile, candidate) in enumerate(rows, start=1)
        ]
    }


@router.get("/health/live")
def liveness():
    return {"status": "ok"}


@router.get("/health/ready")
def readiness(request: Request, db: Session = Depends(get_db)):
    from sqlalchemy import text

    try:
        db.execute(text("SELECT 1"))
        if request.app.state.settings.app_env != "test":
            request.app.state.redis.ping()
    except (SQLAlchemyError, redis.RedisError) as error:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Una dependencia no está disponible."
        ) from error
    return {"status": "ready"}


@router.get("/players/me/ledger")
def get_ledger(
    player=Depends(get_current_player),
    db: Session = Depends(get_db),
):
    user, _profile = player
    points = (
        db.query(PointTransaction)
        .filter(PointTransaction.user_id == user.id)
        .order_by(PointTransaction.created_at.desc())
        .all()
    )
    xp = (
        db.query(XPTransaction)
        .filter(XPTransaction.user_id == user.id)
        .order_by(XPTransaction.created_at.desc())
        .all()
    )
    return {
        "points": [
            {
                "amount": item.amount,
                "collection_id": item.collection_id,
                "created_at": item.created_at,
            }
            for item in points
        ],
        "xp": [
            {
                "amount": item.amount,
                "collection_id": item.collection_id,
                "created_at": item.created_at,
            }
            for item in xp
        ],
    }
