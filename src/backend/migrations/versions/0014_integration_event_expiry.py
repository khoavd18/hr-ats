"""Expire overdue alerts before a new day starts."""

import sqlalchemy as sa
from alembic import op

revision = "0014_integration_event_expiry"
down_revision = "0013_integration_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("integration_events", sa.Column("expires_at", sa.DateTime(timezone=True)))


def downgrade() -> None:
    op.drop_column("integration_events", "expires_at")
