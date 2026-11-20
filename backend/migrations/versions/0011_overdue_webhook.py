"""T34 outbox for private overdue-task reminders."""

import sqlalchemy as sa
from alembic import op

revision = "0011_overdue_webhook"
down_revision = "0010_erased_contacts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "overdue_webhook_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("reminder_day", sa.Date(), nullable=False),
        sa.Column("overdue_count", sa.Integer(), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("user_id", "reminder_day", name="uq_overdue_webhook_user_day"),
        sa.CheckConstraint("overdue_count > 0", name="ck_overdue_webhook_positive_count"),
        sa.CheckConstraint("attempts >= 0", name="ck_overdue_webhook_attempts"),
    )
    op.create_index(
        "ix_overdue_webhook_pending",
        "overdue_webhook_events",
        ["user_id", "next_attempt_at"],
        postgresql_where=sa.text("delivered_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_table("overdue_webhook_events")
