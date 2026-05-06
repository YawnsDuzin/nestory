from sqlalchemy.orm import Session

from app.models import Post
from app.models._enums import PostStatus, PostType
from app.tests.factories import RegionFactory, UserFactory


def test_create_review_post_with_metadata(db: Session) -> None:
    u = UserFactory()
    r = RegionFactory()
    p = Post(
        author_id=u.id,
        region_id=r.id,
        type=PostType.REVIEW,
        title="1년차 후기",
        body="단열이 가장 후회됨",
        metadata_={"satisfaction_overall": 4, "regrets": ["단열"]},
    )
    db.add(p)
    db.flush()
    assert p.id is not None
    assert p.status == PostStatus.DRAFT
    assert p.view_count == 0
    assert p.metadata_["satisfaction_overall"] == 4


def test_plan_post_type(db: Session) -> None:
    u = UserFactory()
    r = RegionFactory()
    p = Post(
        author_id=u.id,
        region_id=r.id,
        type=PostType.PLAN,
        title="우리 가족 정착 계획",
        body="2027년 양평 입주 검토",
        metadata_={"target_move_year": 2027, "open_to_advice": True},
    )
    db.add(p)
    db.flush()
    assert p.type == PostType.PLAN


def test_question_with_parent_link(db: Session) -> None:
    u = UserFactory()
    r = RegionFactory()
    q = Post(author_id=u.id, region_id=r.id, type=PostType.QUESTION, title="Q", body="?")
    db.add(q)
    db.flush()
    a = Post(
        author_id=u.id,
        region_id=r.id,
        type=PostType.ANSWER,
        parent_post_id=q.id,
        title="A",
        body="!",
    )
    db.add(a)
    db.flush()
    assert a.parent_post_id == q.id
