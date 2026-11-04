"""Create persistent player, zone, spawn and economy tables."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_game_core"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("first_name", sa.String(128), nullable=False),
        sa.Column("username", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("telegram_id"),
    )
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"], unique=False)
    op.create_table(
        "player_profiles",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("points", sa.BigInteger(), nullable=False),
        sa.Column("total_xp", sa.BigInteger(), nullable=False),
        sa.Column("collected_count", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("points >= 0", name="ck_player_points_nonnegative"),
        sa.CheckConstraint("total_xp >= 0", name="ck_player_xp_nonnegative"),
        sa.CheckConstraint("collected_count >= 0", name="ck_player_collected_nonnegative"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_table(
        "auth_sessions",
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("token_hash"),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_index("ix_auth_sessions_expires_at", "auth_sessions", ["expires_at"])
    op.create_table(
        "zones",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("boundary_geojson", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_zones_enabled", "zones", ["enabled"])
    op.create_table(
        "collectibles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ticker", sa.String(12), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("symbol", sa.String(8), nullable=False),
        sa.Column("rarity", sa.String(20), nullable=False),
        sa.Column("points_reward", sa.Integer(), nullable=False),
        sa.Column("xp_reward", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticker"),
    )
    op.create_table(
        "spawn_points",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("zone_id", sa.Uuid(), nullable=False),
        sa.Column("collectible_id", sa.Uuid(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("dynamic", sa.Boolean(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("visibility_radius_meters", sa.Integer(), nullable=False),
        sa.Column("collection_radius_meters", sa.Integer(), nullable=False),
        sa.Column("expires_after_seconds", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("latitude >= -90 AND latitude <= 90", name="ck_spawn_point_latitude"),
        sa.CheckConstraint("longitude >= -180 AND longitude <= 180", name="ck_spawn_point_longitude"),
        sa.ForeignKeyConstraint(["zone_id"], ["zones.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["collectible_id"], ["collectibles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_spawn_points_zone_id", "spawn_points", ["zone_id"])
    op.create_table(
        "spawn_instances",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("spawn_point_id", sa.Uuid()),
        sa.Column("zone_id", sa.Uuid(), nullable=False),
        sa.Column("collectible_id", sa.Uuid(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("visibility_radius_meters", sa.Integer(), nullable=False),
        sa.Column("collection_radius_meters", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("latitude >= -90 AND latitude <= 90", name="ck_spawn_latitude"),
        sa.CheckConstraint("longitude >= -180 AND longitude <= 180", name="ck_spawn_longitude"),
        sa.CheckConstraint("state IN ('available', 'collected', 'expired')", name="ck_spawn_state"),
        sa.ForeignKeyConstraint(["spawn_point_id"], ["spawn_points.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["zone_id"], ["zones.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["collectible_id"], ["collectibles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("spawn_point_id", "zone_id", "state", "expires_at"):
        op.create_index(f"ix_spawn_instances_{column}", "spawn_instances", [column])
    op.execute(
        "CREATE INDEX ix_spawn_instances_location_geog ON spawn_instances USING GIST "
        "((ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography))"
    )
    op.create_table(
        "collections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("spawn_instance_id", sa.Uuid(), nullable=False),
        sa.Column("collectible_id", sa.Uuid(), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["spawn_instance_id"], ["spawn_instances.id"]),
        sa.ForeignKeyConstraint(["collectible_id"], ["collectibles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("spawn_instance_id", name="uq_collection_spawn"),
        sa.UniqueConstraint("spawn_instance_id"),
    )
    op.create_index("ix_collections_user_id", "collections", ["user_id"])
    op.create_index("ix_collections_collected_at", "collections", ["collected_at"])
    for table, field in (("point_transactions", "points"), ("xp_transactions", "xp")):
        op.create_table(
            table,
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("collection_id", sa.Uuid(), nullable=False),
            sa.Column("amount", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["collection_id"], ["collections.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("collection_id"),
        )
        op.create_index(f"ix_{table}_user_id", table, ["user_id"])
    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(128), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("response_body", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "key", name="uq_idempotency_user_key"),
    )
    op.create_table(
        "anti_cheat_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("spawn_instance_id", sa.Uuid()),
        sa.Column("reason", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["spawn_instance_id"], ["spawn_instances.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_anti_cheat_events_user_id", "anti_cheat_events", ["user_id"])
    op.create_index("ix_anti_cheat_events_created_at", "anti_cheat_events", ["created_at"])
    op.execute(
        "INSERT INTO collectibles (id, ticker, name, symbol, rarity, points_reward, xp_reward, enabled) VALUES "
        "(gen_random_uuid(), 'BTC', 'Bitcoin', '₿', 'common', 10, 10, true), "
        "(gen_random_uuid(), 'ETH', 'Ethereum', '◆', 'uncommon', 25, 25, true), "
        "(gen_random_uuid(), 'BNB', 'BNB', '⬡', 'rare', 50, 50, true), "
        "(gen_random_uuid(), 'SOL', 'Solana', '◎', 'epic', 100, 100, true)"
    )


def downgrade():
    op.drop_table("anti_cheat_events")
    op.drop_table("idempotency_records")
    op.drop_table("xp_transactions")
    op.drop_table("point_transactions")
    op.drop_table("collections")
    op.execute("DROP INDEX IF EXISTS ix_spawn_instances_location_geog")
    op.drop_table("spawn_instances")
    op.drop_table("spawn_points")
    op.drop_table("collectibles")
    op.drop_table("zones")
    op.drop_table("auth_sessions")
    op.drop_table("player_profiles")
    op.drop_index("ix_users_telegram_id", table_name="users")
    op.drop_table("users")
