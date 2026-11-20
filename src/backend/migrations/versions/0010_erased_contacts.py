"""T29 review F1: erasure markers for CVs accepted before a deletion.

Keyed hashes only (no readable contact); rows are short-lived.
"""

import sqlalchemy as sa
from alembic import op

revision = "0010_erased_contacts"
down_revision = "0009_data_privacy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "erased_contacts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("contact_hash", sa.String(64), nullable=False),
        sa.Column("frozen_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_erased_contacts_contact_hash", "erased_contacts", ["contact_hash"])


def downgrade() -> None:
    op.drop_index("ix_erased_contacts_contact_hash", table_name="erased_contacts")
    op.drop_table("erased_contacts")
