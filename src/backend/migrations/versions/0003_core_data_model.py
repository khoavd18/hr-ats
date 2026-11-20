"""core_data_model"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from app.core.config import get_settings

# Frozen enum values belong to this revision, not to mutable application models.
ENUMS = (
    postgresql.ENUM("upload", "email", "form", "import", name="candidate_source"),
    postgresql.ENUM("client", "department", name="hiring_unit_kind"),
    postgresql.ENUM("draft", "open", "on_hold", "closed", name="job_status"),
    postgresql.ENUM(
        "new",
        "screening",
        "submitted",
        "interview",
        "offer",
        "hired",
        "rejected",
        "withdrawn",
        name="application_stage",
    ),
    postgresql.ENUM("pending", "running", "done", "failed", name="processing_status"),
    postgresql.ENUM("high", "medium", "low", "insufficient", name="ai_level"),
    postgresql.ENUM("pdf_text", "docx", "ocr", "plain", name="extraction_method"),
    postgresql.ENUM(
        "note",
        "call",
        "email_sent",
        "stage_changed",
        "cv_uploaded",
        "ai_scored",
        "ai_feedback",
        "interview_scheduled",
        "offer_made",
        "task_done",
        name="activity_type",
    ),
)


def enum_type(name: str) -> postgresql.ENUM:
    return postgresql.ENUM(name=name, create_type=False)


revision: str = "0003_core_data_model"
down_revision: str | None = "0002_users"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for enum in ENUMS:
        enum.create(op.get_bind(), checkfirst=False)
    op.create_table(
        "candidates",
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("location", sa.String(length=200), nullable=True),
        sa.Column("current_title", sa.String(length=200), nullable=True),
        sa.Column("years_experience", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column(
            "skills",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "languages",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "education",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "experiences",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "source",
            enum_type("candidate_source"),
            server_default=sa.text("'upload'"),
            nullable=False,
        ),
        sa.Column("consent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consent_note", sa.Text(), nullable=True),
        sa.Column("retention_until", sa.Date(), nullable=False),
        sa.Column("anonymized_text", sa.Text(), nullable=True),
        sa.Column("embedding", Vector(get_settings().embedding_dim), nullable=True),
        sa.Column(
            "search_tsv", postgresql.TSVECTOR(), server_default=sa.FetchedValue(), nullable=False
        ),
        sa.Column("merged_into_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("email = lower(email)", name="ck_candidates_email_lowercase"),
        sa.CheckConstraint("years_experience >= 0", name="ck_candidates_experience"),
        sa.ForeignKeyConstraint(
            ["merged_into_id"],
            ["candidates.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_candidates_email"), "candidates", ["email"], unique=False)
    op.create_index(
        "ix_candidates_embedding",
        "candidates",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_index(
        op.f("ix_candidates_merged_into_id"), "candidates", ["merged_into_id"], unique=False
    )
    op.create_index(op.f("ix_candidates_phone"), "candidates", ["phone"], unique=False)
    op.create_index(
        "ix_candidates_search_tsv",
        "candidates",
        ["search_tsv"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_table(
        "hiring_units",
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("kind", enum_type("hiring_unit_kind"), nullable=False),
        sa.Column("contact_name", sa.String(length=200), nullable=True),
        sa.Column("contact_email", sa.String(length=254), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "audit_log",
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("entity", sa.String(length=100), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("ip", postgresql.INET(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_log_actor_id"), "audit_log", ["actor_id"], unique=False)
    op.create_index(op.f("ix_audit_log_entity_id"), "audit_log", ["entity_id"], unique=False)
    op.create_index(op.f("ix_audit_log_occurred_at"), "audit_log", ["occurred_at"], unique=False)
    op.create_table(
        "jobs",
        sa.Column("hiring_unit_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "must_have",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "nice_to_have",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("location", sa.String(length=200), nullable=True),
        sa.Column("employment_type", sa.String(length=100), nullable=True),
        sa.Column("salary_min", sa.Integer(), nullable=True),
        sa.Column("salary_max", sa.Integer(), nullable=True),
        sa.Column("headcount", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("deadline", sa.Date(), nullable=True),
        sa.Column(
            "status", enum_type("job_status"), server_default=sa.text("'draft'"), nullable=False
        ),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("embedding", Vector(get_settings().embedding_dim), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("headcount > 0", name="ck_jobs_headcount"),
        sa.CheckConstraint("salary_min <= salary_max", name="ck_jobs_salary_range"),
        sa.CheckConstraint(
            "salary_min >= 0 AND salary_max >= 0", name="ck_jobs_salary_nonnegative"
        ),
        sa.ForeignKeyConstraint(
            ["hiring_unit_id"],
            ["hiring_units.id"],
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_jobs_hiring_unit_id"), "jobs", ["hiring_unit_id"], unique=False)
    op.create_index(op.f("ix_jobs_owner_id"), "jobs", ["owner_id"], unique=False)
    op.create_index(op.f("ix_jobs_status"), "jobs", ["status"], unique=False)
    op.create_table(
        "applications",
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column(
            "stage", enum_type("application_stage"), server_default=sa.text("'new'"), nullable=False
        ),
        sa.Column(
            "stage_entered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("rejected_reason", sa.Text(), nullable=True),
        sa.Column(
            "ai_status",
            enum_type("processing_status"),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("ai_level", enum_type("ai_level"), nullable=True),
        sa.Column("ai_score", sa.Integer(), nullable=True),
        sa.Column(
            "ai_criteria",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "ai_reasons",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "ai_flags",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("ai_model", sa.String(length=200), nullable=True),
        sa.Column("ai_prompt_version", sa.String(length=100), nullable=True),
        sa.Column("ai_scored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("ai_score BETWEEN 0 AND 100", name="ck_applications_ai_score"),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidates.id"],
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["jobs.id"],
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_applications_job_id"), "applications", ["job_id"], unique=False)
    op.create_index(op.f("ix_applications_owner_id"), "applications", ["owner_id"], unique=False)
    op.create_index(
        "uq_applications_active_candidate_job",
        "applications",
        ["candidate_id", "job_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_table(
        "cv_files",
        sa.Column("candidate_id", sa.Uuid(), nullable=True),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("original_filename", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.String(length=200), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("extraction_method", enum_type("extraction_method"), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("parsed_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "status",
            enum_type("processing_status"),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("parse_model", sa.String(length=200), nullable=True),
        sa.Column("parse_prompt_version", sa.String(length=100), nullable=True),
        sa.Column("uploaded_by", sa.Uuid(), nullable=True),
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("page_count > 0", name="ck_cv_files_page_count"),
        sa.CheckConstraint("size_bytes >= 0", name="ck_cv_files_size"),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidates.id"],
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["jobs.id"],
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sha256"),
    )
    op.create_index(op.f("ix_cv_files_candidate_id"), "cv_files", ["candidate_id"], unique=False)
    op.create_index(op.f("ix_cv_files_job_id"), "cv_files", ["job_id"], unique=False)
    op.create_index(op.f("ix_cv_files_uploaded_by"), "cv_files", ["uploaded_by"], unique=False)
    op.create_table(
        "job_members",
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["jobs.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "user_id", name="uq_job_members_job_user"),
    )
    op.create_index(op.f("ix_job_members_user_id"), "job_members", ["user_id"], unique=False)
    op.create_table(
        "activities",
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("type", enum_type("activity_type"), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.Column("application_id", sa.Uuid(), nullable=True),
        sa.Column("candidate_id", sa.Uuid(), nullable=True),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidates.id"],
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["jobs.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_activities_actor_id"), "activities", ["actor_id"], unique=False)
    op.create_index(
        op.f("ix_activities_application_id"), "activities", ["application_id"], unique=False
    )
    op.create_index(
        op.f("ix_activities_candidate_id"), "activities", ["candidate_id"], unique=False
    )
    op.create_index(op.f("ix_activities_job_id"), "activities", ["job_id"], unique=False)
    op.create_index(op.f("ix_activities_occurred_at"), "activities", ["occurred_at"], unique=False)
    op.create_table(
        "ai_feedback",
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("verdict", sa.String(length=8), nullable=False),
        sa.Column("corrected_level", enum_type("ai_level"), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("verdict IN ('agree', 'disagree')", name="ck_ai_feedback_verdict"),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("application_id", "user_id", name="uq_ai_feedback_application_user"),
    )
    op.create_index(op.f("ix_ai_feedback_user_id"), "ai_feedback", ["user_id"], unique=False)
    op.create_table(
        "stage_events",
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column("from_stage", enum_type("application_stage"), nullable=True),
        sa.Column("to_stage", enum_type("application_stage"), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_stage_events_actor_id"), "stage_events", ["actor_id"], unique=False)
    op.create_index(
        op.f("ix_stage_events_application_id"), "stage_events", ["application_id"], unique=False
    )
    op.create_index(
        op.f("ix_stage_events_occurred_at"), "stage_events", ["occurred_at"], unique=False
    )
    # unaccent is STABLE, so a trigger avoids declaring a mutable dictionary IMMUTABLE.
    # Always overwrite search_tsv, including a direct client assignment to that column.
    op.execute("""
        CREATE FUNCTION public.candidates_update_search_tsv() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            NEW.search_tsv := to_tsvector('simple'::regconfig, public.unaccent(
                coalesce(NEW.full_name, '') || ' ' || coalesce(NEW.current_title, '') || ' ' ||
                coalesce((SELECT string_agg(skill, ' ')
                          FROM jsonb_array_elements_text(NEW.skills) AS skill), '')
            ));
            RETURN NEW;
        END
        $$
    """)
    op.execute("""
        CREATE TRIGGER candidates_search_tsv_trigger
        BEFORE INSERT OR UPDATE ON candidates
        FOR EACH ROW EXECUTE FUNCTION public.candidates_update_search_tsv()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER candidates_search_tsv_trigger ON candidates")
    op.execute("DROP FUNCTION public.candidates_update_search_tsv()")
    op.drop_index(op.f("ix_stage_events_occurred_at"), table_name="stage_events")
    op.drop_index(op.f("ix_stage_events_application_id"), table_name="stage_events")
    op.drop_index(op.f("ix_stage_events_actor_id"), table_name="stage_events")
    op.drop_table("stage_events")
    op.drop_index(op.f("ix_ai_feedback_user_id"), table_name="ai_feedback")
    op.drop_table("ai_feedback")
    op.drop_index(op.f("ix_activities_occurred_at"), table_name="activities")
    op.drop_index(op.f("ix_activities_job_id"), table_name="activities")
    op.drop_index(op.f("ix_activities_candidate_id"), table_name="activities")
    op.drop_index(op.f("ix_activities_application_id"), table_name="activities")
    op.drop_index(op.f("ix_activities_actor_id"), table_name="activities")
    op.drop_table("activities")
    op.drop_index(op.f("ix_job_members_user_id"), table_name="job_members")
    op.drop_table("job_members")
    op.drop_index(op.f("ix_cv_files_uploaded_by"), table_name="cv_files")
    op.drop_index(op.f("ix_cv_files_job_id"), table_name="cv_files")
    op.drop_index(op.f("ix_cv_files_candidate_id"), table_name="cv_files")
    op.drop_table("cv_files")
    op.drop_index(
        "uq_applications_active_candidate_job",
        table_name="applications",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.drop_index(op.f("ix_applications_owner_id"), table_name="applications")
    op.drop_index(op.f("ix_applications_job_id"), table_name="applications")
    op.drop_table("applications")
    op.drop_index(op.f("ix_jobs_status"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_owner_id"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_hiring_unit_id"), table_name="jobs")
    op.drop_table("jobs")
    op.drop_index(op.f("ix_audit_log_occurred_at"), table_name="audit_log")
    op.drop_index(op.f("ix_audit_log_entity_id"), table_name="audit_log")
    op.drop_index(op.f("ix_audit_log_actor_id"), table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_table("hiring_units")
    op.drop_index("ix_candidates_search_tsv", table_name="candidates", postgresql_using="gin")
    op.drop_index(op.f("ix_candidates_phone"), table_name="candidates")
    op.drop_index(op.f("ix_candidates_merged_into_id"), table_name="candidates")
    op.drop_index(
        "ix_candidates_embedding",
        table_name="candidates",
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.drop_index(op.f("ix_candidates_email"), table_name="candidates")
    op.drop_table("candidates")
    for enum in reversed(ENUMS):
        enum.drop(op.get_bind(), checkfirst=False)
