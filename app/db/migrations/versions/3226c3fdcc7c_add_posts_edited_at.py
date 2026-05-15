"""add posts.edited_at

Revision ID: 3226c3fdcc7c
Revises: bc70466dfb57
Create Date: 2026-05-15 23:43:25.194228

"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3226c3fdcc7c'
down_revision: str | Sequence[str] | None = 'bc70466dfb57'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('posts', sa.Column('edited_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('posts', 'edited_at')
