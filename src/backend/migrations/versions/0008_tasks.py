"""T25 tasks (additive; rollback only on disposable databases)."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008_tasks"
down_revision = "0007_inbound_emails"
branch_labels = None
depends_on = None


def upgrade() -> None:
    status = postgresql.ENUM("todo", "doing", "done", "cancelled", name="task_status")
    status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "tasks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("assignee_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("job_id", sa.Uuid(), sa.ForeignKey("jobs.id")),
        sa.Column("application_id", sa.Uuid(), sa.ForeignKey("applications.id")),
        sa.Column("due_at", sa.DateTime(timezone=True)),
        sa.Column(
            "status",
            postgresql.ENUM(name="task_status", create_type=False),
            nullable=False,
            server_default=sa.text("'todo'"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("length(trim(title)) > 0", name="ck_tasks_title"),
        sa.CheckConstraint(
            "(status = 'done') = (completed_at IS NOT NULL)", name="ck_tasks_completed"
        ),
        sa.CheckConstraint("application_id IS NULL OR job_id IS NOT NULL", name="ck_tasks_job"),
    )
    for column in ("created_by", "job_id", "application_id"):
        op.create_index(f"ix_tasks_{column}", "tasks", [column])
    op.create_index("ix_tasks_assignee_status_due", "tasks", ["assignee_id", "status", "due_at"])


def downgrade() -> None:
    op.drop_table("tasks")
    postgresql.ENUM(name="task_status").drop(op.get_bind(), checkfirst=True)
