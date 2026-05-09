"""add region scoring weights

Revision ID: 7f8c2d4a6e91
Revises: e1ad6f3c4a92
Create Date: 2026-05-08 12:00:00.000000

"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7f8c2d4a6e91'
down_revision: str | Sequence[str] | None = 'e1ad6f3c4a92'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'region_scoring_weights',
        sa.Column('region_id', sa.Integer(), nullable=False),
        sa.Column('activity_score', sa.Integer(), nullable=False),
        sa.Column('medical_score', sa.Integer(), nullable=False),
        sa.Column('family_visit_score', sa.Integer(), nullable=False),
        sa.Column('farming_score', sa.Integer(), nullable=False),
        sa.Column('budget_score', sa.Integer(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['region_id'], ['regions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['updated_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('region_id'),
    )
    op.execute(
        """
        INSERT INTO region_scoring_weights
            (region_id, activity_score, medical_score, family_visit_score,
             farming_score, budget_score, notes, updated_at)
        SELECT r.id, v.activity, v.medical, v.family_visit,
               v.farming, v.budget, v.notes, now()
        FROM regions r
        JOIN (VALUES
            ('yangpyeong', 8, 7, 9, 7, 6,
             '양평군: 한강·산림 활동 풍부, 의료 양호, 자녀 1시간 거리, 텃밭 적합, 시세 중상.'),
            ('yeongwol',   7, 4, 4, 8, 9,
             '영월군: 자연·산림 활동 풍부, 의료 약함, 수도권 멀음, 농지 좋음, 시세 매우 저렴.'),
            ('hongcheon',  8, 6, 7, 8, 7,
             '홍천군: 자연 활동 강함, 의료 보통, 수도권 1.5시간, 농지 풍부, 시세 중간.'),
            ('gokseong',   6, 5, 4, 9, 9,
             '곡성군: 농사 환경 최상, 시세 저렴, 자녀 방문 약함, 의료 보통.')
        ) AS v(slug, activity, medical, family_visit, farming, budget, notes)
            ON r.slug = v.slug
        ON CONFLICT (region_id) DO UPDATE SET
            activity_score = EXCLUDED.activity_score,
            medical_score = EXCLUDED.medical_score,
            family_visit_score = EXCLUDED.family_visit_score,
            farming_score = EXCLUDED.farming_score,
            budget_score = EXCLUDED.budget_score,
            notes = EXCLUDED.notes,
            updated_at = now()
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("region_scoring_weights")
