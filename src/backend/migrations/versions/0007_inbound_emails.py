"""T24: email intake records and file provenance."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007_inbound_emails"
down_revision = "0006_email_templates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cv_files",
        sa.Column(
            "source",
            postgresql.ENUM(name="candidate_source", create_type=False),
            nullable=False,
            server_default="upload",
        ),
    )
    op.create_table(
        "inbound_emails",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("message_id", sa.Text(), nullable=False, unique=True),
        sa.Column("from_email", sa.String(254), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attachment_count", sa.Integer(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error", sa.Text()),
        sa.CheckConstraint("attachment_count >= 0", name="ck_inbound_emails_attachment_count"),
        sa.CheckConstraint("status IN ('processed', 'ignored')", name="ck_inbound_emails_status"),
    )


def downgrade() -> None:
    op.drop_table("inbound_emails")
    op.drop_column("cv_files", "source")
