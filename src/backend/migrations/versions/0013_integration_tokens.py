"""Store expiring, scoped service tokens."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0013_integration_tokens"
down_revision = "0012_integration_outbox"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "integration_tokens",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "sponsor_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("scopes", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "cardinality(scopes) BETWEEN 1 AND 3 AND "
            "scopes <@ ARRAY['tasks:create', 'reports:summary', 'cv:upload']::varchar[] "
            "AND array_position(scopes, NULL::varchar) IS NULL",
            name="ck_integration_token_scopes",
        ),
    )


def downgrade() -> None:
    op.drop_table("integration_tokens")
