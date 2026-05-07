from sqlalchemy.orm import Session

from app.models._enums import PostStatus, PostType
from app.tests.factories import (
    AnswerPostFactory,
    PlanPostFactory,
    QuestionPostFactory,
    ReviewPostFactory,
)


def test_create_review_post_with_metadata(db: Session) -> None:
    p = ReviewPostFactory(
        title="1년차 후기",
        body="단열이 가장 후회됨",
        metadata_={"satisfaction_overall": 4, "regrets": ["단열"]},
    )
    assert p.id is not None
    assert p.status == PostStatus.DRAFT
    assert p.view_count == 0
    assert p.metadata_["satisfaction_overall"] == 4


def test_plan_post_type(db: Session) -> None:
    p = PlanPostFactory(
        title="우리 가족 정착 계획",
        body="2027년 양평 입주 검토",
        metadata_={"target_move_year": 2027, "open_to_advice": True},
    )
    assert p.type == PostType.PLAN


def test_question_with_parent_link(db: Session) -> None:
    q = QuestionPostFactory(title="Q", body="?")
    a = AnswerPostFactory(
        author_id=q.author_id,
        region_id=q.region_id,
        parent_post=q,
        title="A",
        body="!",
    )
    assert a.parent_post_id == q.id
