"""T29 retention tombstones and administrative data requests.

Downgrade refuses after privacy processing: erased data cannot be reconstructed.
"""

import sqlalchemy as sa
from alembic import op

revision = "0009_data_privacy"
down_revision = "0008_tasks"
branch_labels = None
depends_on = None

NULLABLE = {
    "candidates": ("full_name", "skills", "languages", "education", "experiences", "search_tsv"),
    "cv_files": ("storage_key", "original_filename", "sha256"),
    "applications": ("ai_criteria", "ai_reasons", "ai_flags"),
    "email_messages": ("to_email", "cc", "subject", "body_html"),
    "inbound_emails": ("message_id", "from_email", "subject"),
    "tasks": ("title",),
    "interviews": ("interviewers",),
    "audit_log": ("actor_id",),
}


def search_function(privacy: bool) -> None:
    guard = (
        "IF NEW.purge_pending_at IS NOT NULL THEN NEW.search_tsv := NULL; RETURN NEW; END IF;"
        if privacy
        else ""
    )
    op.execute(f"""
        CREATE OR REPLACE FUNCTION public.candidates_update_search_tsv() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            {guard}
            NEW.search_tsv := to_tsvector('simple'::regconfig, public.unaccent(
                coalesce(NEW.full_name, '') || ' ' || coalesce(NEW.current_title, '') || ' ' ||
                coalesce((SELECT string_agg(skill, ' ')
                          FROM jsonb_array_elements_text(NEW.skills) AS skill), '')
            ));
            RETURN NEW;
        END;
        $$
    """)


def upgrade() -> None:
    for column in ("expired_at", "purge_pending_at", "purged_at"):
        op.add_column("candidates", sa.Column(column, sa.DateTime(timezone=True)))
    op.create_index("ix_candidates_retention_until", "candidates", ["retention_until"])
    for table, columns in NULLABLE.items():
        for column in columns:
            op.alter_column(table, column, nullable=True)
    search_function(True)
    op.create_table(
        "data_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("candidate_id", sa.Uuid(), sa.ForeignKey("candidates.id"), nullable=False),
        sa.Column("kind", sa.String(6), nullable=False),
        sa.Column("requested_by_note", sa.Text()),
        sa.Column("status", sa.String(8), nullable=False, server_default=sa.text("'open'")),
        sa.Column("handled_by", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("handled_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("kind IN ('delete', 'export')", name="ck_data_requests_kind"),
        sa.CheckConstraint(
            "status IN ('open', 'done', 'rejected')", name="ck_data_requests_status"
        ),
        sa.CheckConstraint(
            "(status = 'open' AND handled_at IS NULL AND handled_by IS NULL) OR "
            "(status <> 'open' AND handled_at IS NOT NULL)",
            name="ck_data_requests_handled",
        ),
    )
    op.create_index("ix_data_requests_candidate_id", "data_requests", ["candidate_id"])


def downgrade() -> None:
    # Never invent names, file hashes, request history or a system user's identity.
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM candidates WHERE purge_pending_at IS NOT NULL)
                OR EXISTS (SELECT 1 FROM audit_log WHERE actor_id IS NULL)
                OR EXISTS (SELECT 1 FROM data_requests)
            THEN RAISE EXCEPTION 'Privacy data exists; forward migration required'; END IF;
        END $$
    """)
    op.drop_table("data_requests")
    search_function(False)
    for table, columns in NULLABLE.items():
        for column in columns:
            op.alter_column(table, column, nullable=False)
    op.drop_index("ix_candidates_retention_until", table_name="candidates")
    for column in ("purged_at", "purge_pending_at", "expired_at"):
        op.drop_column("candidates", column)
