from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    first_name: Mapped[str] = mapped_column(String(128), default="")
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PlayerProfile(Base):
    __tablename__ = "player_profiles"
    __table_args__ = (
        CheckConstraint("points >= 0", name="ck_player_points_nonnegative"),
        CheckConstraint("total_xp >= 0", name="ck_player_xp_nonnegative"),
        CheckConstraint("collected_count >= 0", name="ck_player_collected_nonnegative"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    points: Mapped[int] = mapped_column(BigInteger, default=0)
    total_xp: Mapped[int] = mapped_column(BigInteger, default=0)
    collected_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Zone(Base):
    __tablename__ = "zones"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(120))
    boundary_geojson: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Collectible(Base):
    __tablename__ = "collectibles"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    ticker: Mapped[str] = mapped_column(String(12), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    symbol: Mapped[str] = mapped_column(String(8))
    rarity: Mapped[str] = mapped_column(String(20))
    points_reward: Mapped[int] = mapped_column(Integer)
    xp_reward: Mapped[int] = mapped_column(Integer)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class SpawnPoint(Base):
    __tablename__ = "spawn_points"
    __table_args__ = (
        CheckConstraint("latitude >= -90 AND latitude <= 90", name="ck_spawn_point_latitude"),
        CheckConstraint("longitude >= -180 AND longitude <= 180", name="ck_spawn_point_longitude"),
        CheckConstraint(
            "visibility_radius_meters BETWEEN 1 AND 5000", name="ck_spawn_point_visibility_radius"
        ),
        CheckConstraint(
            "collection_radius_meters BETWEEN 1 AND 35", name="ck_spawn_point_collection_radius"
        ),
        CheckConstraint(
            "expires_after_seconds BETWEEN 60 AND 604800", name="ck_spawn_point_expiration"
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    zone_id: Mapped[UUID] = mapped_column(ForeignKey("zones.id", ondelete="CASCADE"), index=True)
    collectible_id: Mapped[UUID] = mapped_column(ForeignKey("collectibles.id"))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    dynamic: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    visibility_radius_meters: Mapped[int] = mapped_column(Integer, default=1_500)
    collection_radius_meters: Mapped[int] = mapped_column(Integer, default=35)
    expires_after_seconds: Mapped[int] = mapped_column(Integer, default=86_400)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SpawnInstance(Base):
    __tablename__ = "spawn_instances"
    __table_args__ = (
        CheckConstraint("latitude >= -90 AND latitude <= 90", name="ck_spawn_latitude"),
        CheckConstraint("longitude >= -180 AND longitude <= 180", name="ck_spawn_longitude"),
        CheckConstraint(
            "visibility_radius_meters BETWEEN 1 AND 5000", name="ck_spawn_visibility_radius"
        ),
        CheckConstraint(
            "collection_radius_meters BETWEEN 1 AND 35", name="ck_spawn_collection_radius"
        ),
        CheckConstraint("state IN ('available', 'collected', 'expired')", name="ck_spawn_state"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    spawn_point_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("spawn_points.id", ondelete="SET NULL"), nullable=True, index=True
    )
    zone_id: Mapped[UUID] = mapped_column(ForeignKey("zones.id", ondelete="CASCADE"), index=True)
    collectible_id: Mapped[UUID] = mapped_column(ForeignKey("collectibles.id"))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    visibility_radius_meters: Mapped[int] = mapped_column(Integer)
    collection_radius_meters: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(16), default="available", index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Collection(Base):
    __tablename__ = "collections"
    __table_args__ = (UniqueConstraint("spawn_instance_id", name="uq_collection_spawn"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    spawn_instance_id: Mapped[UUID] = mapped_column(ForeignKey("spawn_instances.id"))
    collectible_id: Mapped[UUID] = mapped_column(ForeignKey("collectibles.id"))
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class PointTransaction(Base):
    __tablename__ = "point_transactions"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    collection_id: Mapped[UUID] = mapped_column(ForeignKey("collections.id"), unique=True)
    amount: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class XPTransaction(Base):
    __tablename__ = "xp_transactions"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    collection_id: Mapped[UUID] = mapped_column(ForeignKey("collections.id"), unique=True)
    amount: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (UniqueConstraint("user_id", "key", name="uq_idempotency_user_key"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    key: Mapped[str] = mapped_column(String(128))
    request_hash: Mapped[str] = mapped_column(String(64))
    response_body: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AntiCheatEvent(Base):
    __tablename__ = "anti_cheat_events"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    spawn_instance_id: Mapped[UUID | None] = mapped_column(ForeignKey("spawn_instances.id"), nullable=True)
    reason: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
