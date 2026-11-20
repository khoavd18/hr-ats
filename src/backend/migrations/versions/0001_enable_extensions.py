"""Enable the PostgreSQL extensions required by the application."""

from alembic import op

revision: str = "0001_enable_extensions"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")


def downgrade() -> None:
    # T01 can provision these extensions before Alembic. Keep shared extensions on rollback.
    pass
