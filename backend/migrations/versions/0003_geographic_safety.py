"""Add auditable geographic safety evidence without changing legacy zones."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_geographic_safety"
down_revision = "0002_wallet_auth"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "geographic_security_evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("geometry_geojson", sa.Text(), nullable=True),
        sa.Column("security_status", sa.String(16), nullable=False),
        sa.Column("place_type", sa.String(64), nullable=False),
        sa.Column("source_name", sa.String(160), nullable=True),
        sa.Column("source_identifier", sa.String(255), nullable=True),
        sa.Column("license_terms", sa.String(512), nullable=True),
        sa.Column("access_status", sa.String(24), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("validation_status", sa.String(24), nullable=False),
        sa.Column("rule_applied", sa.String(128), nullable=True),
        sa.Column("policy_version", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "security_status IN ('safe', 'caution', 'restricted', 'unknown')",
            name="ck_geo_security_status",
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_geo_security_confidence",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        "ALTER TABLE geographic_security_evidence "
        "ADD COLUMN geom geometry(Geometry, 4326)"
    )
    op.create_index(
        "ix_geographic_security_evidence_expires_at",
        "geographic_security_evidence",
        ["expires_at"],
    )
    op.execute(
        "CREATE INDEX ix_geo_security_evidence_geom "
        "ON geographic_security_evidence USING GIST (geom)"
    )

    op.create_table(
        "geographic_security_audit_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("evidence_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("actor", sa.String(160), nullable=False),
        sa.Column(
            "previous_value",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
        sa.Column(
            "new_value",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_geographic_security_audit_logs_evidence_id",
        "geographic_security_audit_logs",
        ["evidence_id"],
    )


def downgrade():
    op.drop_index(
        "ix_geographic_security_audit_logs_evidence_id",
        table_name="geographic_security_audit_logs",
    )
    op.drop_table("geographic_security_audit_logs")
    op.drop_index(
        "ix_geo_security_evidence_geom",
        table_name="geographic_security_evidence",
    )
    op.drop_index(
        "ix_geographic_security_evidence_expires_at",
        table_name="geographic_security_evidence",
    )
    op.drop_table("geographic_security_evidence")
