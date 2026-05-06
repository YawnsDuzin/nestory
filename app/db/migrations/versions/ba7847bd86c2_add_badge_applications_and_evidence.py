"""add badge applications and evidence

Revision ID: ba7847bd86c2
Revises: 18fd0e2d11d9
Create Date: 2026-05-06 15:18:10.568416

"""
from typing import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'ba7847bd86c2'
down_revision: str | Sequence[str] | None = '18fd0e2d11d9'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "badge_applications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "requested_level",
            sa.Enum("region_verified", "resident", name="badge_requested_level"),
            nullable=False,
        ),
        sa.Column("region_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "approved", "rejected", name="badge_application_status"),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("reviewer_id", sa.Integer(), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column(
            "applied_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["region_id"], ["regions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_badge_applications_status"),
        "badge_applications",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_badge_applications_user_id"),
        "badge_applications",
        ["user_id"],
        unique=False,
    )
    op.create_table(
        "badge_evidence",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column(
            "evidence_type",
            sa.Enum(
                "utility_bill",
                "contract",
                "building_cert",
                "geo_selfie",
                name="evidence_type",
            ),
            nullable=False,
        ),
        sa.Column("file_path", sa.String(length=512), nullable=False),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("scheduled_delete_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["application_id"], ["badge_applications.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_badge_evidence_application_id"),
        "badge_evidence",
        ["application_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_badge_evidence_application_id"), table_name="badge_evidence")
    op.drop_table("badge_evidence")
    op.drop_index(op.f("ix_badge_applications_status"), table_name="badge_applications")
    op.drop_index(op.f("ix_badge_applications_user_id"), table_name="badge_applications")
    op.drop_table("badge_applications")
    op.execute("DROP TYPE evidence_type")
    op.execute("DROP TYPE badge_application_status")
    op.execute("DROP TYPE badge_requested_level")
