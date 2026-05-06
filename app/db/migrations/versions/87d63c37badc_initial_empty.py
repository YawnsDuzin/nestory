"""initial empty

Revision ID: 87d63c37badc
Revises:
Create Date: 2026-04-20 09:47:08.323370

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "87d63c37badc"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
