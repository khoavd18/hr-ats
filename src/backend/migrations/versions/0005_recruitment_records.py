"""Add interviews, offers and a unique placement per application."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_recruitment_records"
down_revision: str | None = "0004_audit_details"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _record_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("application_id", sa.Uuid(), sa.ForeignKey("applications.id"), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "interviews",
        *_record_columns(),
        sa.Column("round", sa.Integer(), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("location_or_link", sa.Text()),
        sa.Column(
            "interviewers",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("result", sa.String(10), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("feedback", sa.Text()),
        sa.CheckConstraint("round > 0", name="ck_interviews_round"),
        sa.CheckConstraint("duration_minutes BETWEEN 1 AND 1440", name="ck_interviews_duration"),
        sa.CheckConstraint(
            "result IN ('pending', 'pass', 'fail', 'no_show')", name="ck_interviews_result"
        ),
        sa.CheckConstraint(
            "jsonb_typeof(interviewers) = 'array'", name="ck_interviews_interviewers"
        ),
    )
    op.create_index("ix_interviews_application_id", "interviews", ["application_id"])
    op.create_index("ix_interviews_scheduled_at", "interviews", ["scheduled_at"])
    op.create_table(
        "offers",
        *_record_columns(),
        sa.Column("salary", sa.Integer()),
        sa.Column("start_date", sa.Date()),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(8), server_default=sa.text("'draft'"), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.CheckConstraint("salary >= 0", name="ck_offers_salary"),
        sa.CheckConstraint(
            "status IN ('draft', 'sent', 'accepted', 'declined')", name="ck_offers_status"
        ),
        sa.CheckConstraint(
            "(status = 'draft' AND sent_at IS NULL) OR (status <> 'draft' AND sent_at IS NOT NULL)",
            name="ck_offers_sent_at",
        ),
    )
    op.create_index("ix_offers_application_id", "offers", ["application_id"])
    op.create_table(
        "placements",
        *_record_columns(),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("fee_amount", sa.Integer()),
        sa.Column("guarantee_until", sa.Date()),
        sa.Column("status", sa.String(17), server_default=sa.text("'active'"), nullable=False),
        sa.UniqueConstraint("application_id", name="uq_placements_application"),
        sa.CheckConstraint("fee_amount >= 0", name="ck_placements_fee"),
        sa.CheckConstraint("guarantee_until >= start_date", name="ck_placements_guarantee"),
        sa.CheckConstraint(
            "status IN ('active', 'left_in_guarantee', 'completed')", name="ck_placements_status"
        ),
    )


def downgrade() -> None:
    # Only used on the disposable migration-test database; existing deployments back up first.
    op.drop_table("placements")
    op.drop_table("offers")
    op.drop_table("interviews")
