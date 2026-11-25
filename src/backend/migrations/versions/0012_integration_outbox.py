"""Add the signed webhook outbox."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0012_integration_outbox"
down_revision = "0011_overdue_webhook"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "webhook_endpoints",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("path", sa.String(200), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.UniqueConstraint("path", name="uq_webhook_endpoint_path"),
        sa.CheckConstraint(
            "path ~ '^/webhook/hr-ats/[a-z0-9-]+(/[a-z0-9-]+)*$'", name="ck_webhook_endpoint_path"
        ),
    )
    op.create_table(
        "integration_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("endpoint_id", sa.Uuid(), sa.ForeignKey("webhook_endpoints.id"), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("dedupe_key", sa.Uuid(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.Column("failed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint(
            "endpoint_id", "event_type", "dedupe_key", name="uq_integration_event_delivery"
        ),
        sa.CheckConstraint("attempts BETWEEN 0 AND 4", name="ck_integration_event_attempts"),
        sa.CheckConstraint(
            "delivered_at IS NULL OR failed_at IS NULL", name="ck_integration_event_outcome"
        ),
        sa.CheckConstraint("jsonb_typeof(payload) = 'object'", name="ck_integration_event_payload"),
    )
    op.create_index(
        "ix_integration_event_pending",
        "integration_events",
        ["next_attempt_at", "id"],
        postgresql_where=sa.text("delivered_at IS NULL AND failed_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_table("integration_events")
    op.drop_table("webhook_endpoints")
