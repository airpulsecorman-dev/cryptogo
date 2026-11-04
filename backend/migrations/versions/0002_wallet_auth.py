"""Add independent wallet identities and one-time authentication challenges."""

from alembic import op
import sqlalchemy as sa

revision = "0002_wallet_auth"
down_revision = "0001_game_core"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "users",
        "telegram_id",
        existing_type=sa.BigInteger(),
        nullable=True,
    )
    op.create_table(
        "wallet_identities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("network", sa.String(32), nullable=False),
        sa.Column("address", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider", "network", "address", name="uq_wallet_identity"
        ),
    )
    op.create_index("ix_wallet_identities_user_id", "wallet_identities", ["user_id"])
    op.create_table(
        "auth_challenges",
        sa.Column("nonce", sa.String(64), nullable=False),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("address", sa.String(128)),
        sa.Column("network", sa.String(32)),
        sa.Column("domain", sa.String(255), nullable=False),
        sa.Column("uri", sa.String(512), nullable=False),
        sa.Column("message", sa.Text()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("nonce"),
    )
    op.create_index("ix_auth_challenges_provider", "auth_challenges", ["provider"])
    op.create_index("ix_auth_challenges_expires_at", "auth_challenges", ["expires_at"])


def downgrade():
    op.drop_index("ix_auth_challenges_expires_at", table_name="auth_challenges")
    op.drop_index("ix_auth_challenges_provider", table_name="auth_challenges")
    op.drop_table("auth_challenges")
    op.drop_index("ix_wallet_identities_user_id", table_name="wallet_identities")
    op.drop_table("wallet_identities")
    op.alter_column(
        "users",
        "telegram_id",
        existing_type=sa.BigInteger(),
        nullable=False,
    )
