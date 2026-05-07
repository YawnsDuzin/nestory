"""p14 search indexes (pg_trgm + simple FTS)

Revision ID: e1ad6f3c4a92
Revises: 1c683806cbae
Create Date: 2026-05-08 09:30:00.000000

"""
from typing import Sequence

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'e1ad6f3c4a92'
down_revision: str | Sequence[str] | None = '1c683806cbae'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        "CREATE INDEX ix_posts_search_trgm ON posts "
        "USING GIN ((title || ' ' || body) gin_trgm_ops) "
        "WHERE status = 'published' AND deleted_at IS NULL"
    )
    op.execute(
        "CREATE INDEX ix_posts_search_fts ON posts "
        "USING GIN (to_tsvector('simple', title || ' ' || body)) "
        "WHERE status = 'published' AND deleted_at IS NULL"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX IF EXISTS ix_posts_search_fts")
    op.execute("DROP INDEX IF EXISTS ix_posts_search_trgm")
