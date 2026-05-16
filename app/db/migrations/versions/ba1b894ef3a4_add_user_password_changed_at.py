"""add user password_changed_at

Revision ID: ba1b894ef3a4
Revises: 3226c3fdcc7c
Create Date: 2026-05-16 12:16:37.291785

"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ba1b894ef3a4'
down_revision: str | Sequence[str] | None = '3226c3fdcc7c'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('password_changed_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('users', 'password_changed_at')
