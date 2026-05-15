"""update_* / soft_delete_post 서비스 함수 단위 테스트."""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models._enums import PostStatus, PostType
from app.schemas.post_metadata import PlanMetadata, QuestionMetadata
from app.services import posts as posts_service
from app.tests.factories import PostFactory, UserFactory


def test_update_question_changes_title_body_tags(db: Session) -> None:
    author = UserFactory()
    post = PostFactory(
        author=author, author_id=author.id,
        type=PostType.QUESTION, status=PostStatus.PUBLISHED,
        title="기존 제목", body="기존 본문",
        metadata_={"__post_type__": "question", "tags": ["old"]},
    )
    db.flush()
    payload = QuestionMetadata(tags=["new1", "new2"])
    updated = posts_service.update_question(
        db, post, payload=payload, title="새 제목", body="새 본문"
    )
    assert updated.title == "새 제목"
    assert updated.body == "새 본문"
    assert updated.metadata_["tags"] == ["new1", "new2"]
    assert updated.edited_at is not None
    assert updated.type == PostType.QUESTION  # 불변
    assert updated.author_id == author.id     # 불변


def test_update_question_sets_edited_at_close_to_now(db: Session) -> None:
    post = PostFactory(type=PostType.QUESTION, status=PostStatus.PUBLISHED)
    db.flush()
    before = datetime.now(UTC)
    posts_service.update_question(
        db, post,
        payload=QuestionMetadata(tags=[]),
        title="t", body="b",
    )
    after = datetime.now(UTC)
    assert post.edited_at is not None
    assert before <= post.edited_at <= after


def test_update_answer_changes_body_only(db: Session) -> None:
    question = PostFactory(type=PostType.QUESTION, status=PostStatus.PUBLISHED)
    author = UserFactory()
    answer = PostFactory(
        author=author, author_id=author.id,
        type=PostType.ANSWER, status=PostStatus.PUBLISHED,
        parent_post_id=question.id,
        body="기존 답변",
        metadata_={"__post_type__": "answer"},
    )
    db.flush()
    posts_service.update_answer(db, answer, body="수정된 답변")
    assert answer.body == "수정된 답변"
    assert answer.edited_at is not None
    assert answer.parent_post_id == question.id  # 불변
    assert answer.type == PostType.ANSWER         # 불변


def test_update_answer_rejects_non_answer(db: Session) -> None:
    import pytest
    q = PostFactory(type=PostType.QUESTION, status=PostStatus.PUBLISHED)
    db.flush()
    with pytest.raises(ValueError):
        posts_service.update_answer(db, q, body="x")


def test_update_plan_changes_all_metadata_fields(db: Session) -> None:
    author = UserFactory()
    post = PostFactory(
        author=author, author_id=author.id,
        type=PostType.PLAN, status=PostStatus.PUBLISHED,
        title="기존", body="기존",
        metadata_={
            "__post_type__": "plan",
            "target_move_year": 2027,
            "household_size": 1,
            "budget_total_manwon_band": "<5000",
            "construction_intent": "undecided",
            "open_to_advice": True,
        },
    )
    db.flush()
    new_payload = PlanMetadata(
        target_move_year=2028,
        budget_total_manwon_band="10000-20000",
        construction_intent="self_build",
    )
    posts_service.update_plan(
        db, post, payload=new_payload, title="새 제목", body="새 본문"
    )
    assert post.title == "새 제목"
    assert post.body == "새 본문"
    assert post.metadata_["target_move_year"] == 2028
    assert post.metadata_["budget_total_manwon_band"] == "10000-20000"
    assert post.metadata_["construction_intent"] == "self_build"
    assert post.edited_at is not None
    assert post.type == PostType.PLAN
