"""Comments service — create + list with 1-level reply tree."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Comment, Post, User
from app.models._enums import CommentStatus, NotificationType
from app.services.notifications import create_notification

MAX_BODY = 2000


class CommentValidationError(ValueError):
    """Raised when comment input fails validation."""


def create_comment(
    db: Session, post: Post, user: User, body: str, *, parent_id: int | None = None
) -> Comment:
    body = (body or "").strip()
    if not body:
        raise CommentValidationError("본문이 비어있습니다")
    if len(body) > MAX_BODY:
        raise CommentValidationError("댓글이 너무 깁니다")
    if parent_id:
        parent = db.get(Comment, parent_id)
        if not parent or parent.post_id != post.id or parent.parent_id is not None:
            raise CommentValidationError("잘못된 부모 댓글입니다")
    c = Comment(post_id=post.id, author_id=user.id, body=body, parent_id=parent_id)
    db.add(c)
    post_author = db.get(User, post.author_id)
    if post_author is not None:
        create_notification(
            db,
            recipient=post_author,
            type=NotificationType.POST_COMMENT,
            source_user=user,
            target_type="post",
            target_id=post.id,
        )
    db.commit()
    db.refresh(c)
    return c


def list_comments(db: Session, post: Post) -> list[Comment]:
    return list(
        db.scalars(
            select(Comment)
            .where(
                Comment.post_id == post.id,
                Comment.status == CommentStatus.VISIBLE,
                Comment.deleted_at.is_(None),
            )
            .order_by(Comment.parent_id.is_(None).desc(), Comment.created_at.asc())
        ).all()
    )
