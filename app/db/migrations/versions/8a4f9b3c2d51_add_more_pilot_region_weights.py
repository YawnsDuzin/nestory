"""add more pilot region weights (gapyeong/namyangju/chuncheon)

Revision ID: 8a4f9b3c2d51
Revises: 7f8c2d4a6e91
Create Date: 2026-05-08 23:50:00.000000

"""
from typing import Sequence

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '8a4f9b3c2d51'
down_revision: str | Sequence[str] | None = '7f8c2d4a6e91'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema — supplement scoring weights for additional pilot regions.

    Migration 7f8c2d4a6e91 weighted 4 dev pilots (yangpyeong/yeongwol/hongcheon/gokseong).
    scripts/seed_regions.py creates 5 prod pilots (yangpyeong/gapyeong/namyangju/
    chuncheon/hongcheon). This migration adds weights for the 3 prod pilots not yet
    covered: gapyeong, namyangju, chuncheon. Idempotent UPSERT.
    """
    op.execute(
        """
        INSERT INTO region_scoring_weights
            (region_id, activity_score, medical_score, family_visit_score,
             farming_score, budget_score, notes, updated_at)
        SELECT r.id, v.activity, v.medical, v.family_visit,
               v.farming, v.budget, v.notes, now()
        FROM regions r
        JOIN (VALUES
            ('gapyeong',  8, 5, 8, 8, 7,
             '가평군: 자연 활동 강함, 의료 보통, 수도권 1시간, 농지 풍부, 시세 중간.'),
            ('namyangju', 7, 8, 10, 5, 5,
             '남양주시: 도심 의료·문화 풍부, 자녀 방문 최상(서울 인접), 농지 보통, 시세 중상.'),
            ('chuncheon', 7, 8, 6, 6, 7,
             '춘천시: 도심 의료·문화 풍부, 자녀 방문 보통, 농사 보통, 시세 중간.')
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
    """Downgrade schema — remove weights for the 3 supplementary pilots."""
    op.execute(
        """
        DELETE FROM region_scoring_weights
        WHERE region_id IN (
            SELECT id FROM regions
            WHERE slug IN ('gapyeong', 'namyangju', 'chuncheon')
        )
        """
    )
