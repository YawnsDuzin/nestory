"""Search service — pg_trgm + simple FTS hybrid post search."""
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import Post
from app.models._enums import PostStatus, PostType

PAGE_SIZE = 20
MIN_QUERY_LEN = 2
MAX_QUERY_LEN = 200
SIMILARITY_THRESHOLD = 0.1


@dataclass
class SearchResult:
    posts: list[Post]
    total: int
    page: int


def normalize_query(q: str) -> str:
    """Strip whitespace and cap length. Returns "" if below MIN_QUERY_LEN."""
    s = (q or "").strip()[:MAX_QUERY_LEN]
    return s if len(s) >= MIN_QUERY_LEN else ""


def search_posts(
    db: Session,
    q: str,
    *,
    region_id: int | None = None,
    post_type: PostType | None = None,
    sort: Literal["relevance", "latest", "popular"] = "relevance",
    page: int = 1,
) -> SearchResult:
    """Search published posts via trgm similarity + simple FTS.

    Short-circuits to empty result for blank / 1-char queries (no DB round-trip).
    Predicates match partial GIN indexes (status=PUBLISHED AND deleted_at IS NULL).
    """
    q = normalize_query(q)
    if not q:
        return SearchResult(posts=[], total=0, page=page)

    base = (
        select(Post)
        .where(Post.status == PostStatus.PUBLISHED, Post.deleted_at.is_(None))
        .options(selectinload(Post.author), selectinload(Post.region))
    )

    tsquery = func.plainto_tsquery("simple", q)
    similarity = func.greatest(
        func.similarity(Post.title, q),
        func.similarity(Post.body, q),
    )
    match_clause = or_(
        func.to_tsvector("simple", Post.title + " " + Post.body).op("@@")(tsquery),
        similarity > SIMILARITY_THRESHOLD,
    )
    stmt = base.where(match_clause)

    if region_id:
        stmt = stmt.where(Post.region_id == region_id)
    if post_type:
        stmt = stmt.where(Post.type == post_type)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    if sort == "latest":
        stmt = stmt.order_by(Post.published_at.desc())
    elif sort == "popular":
        stmt = stmt.order_by(Post.view_count.desc(), Post.published_at.desc())
    else:  # relevance
        stmt = stmt.order_by(similarity.desc(), Post.published_at.desc())

    stmt = stmt.offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)
    posts = list(db.scalars(stmt).all())
    return SearchResult(posts=posts, total=total, page=page)


__all__ = [
    "PAGE_SIZE",
    "MIN_QUERY_LEN",
    "MAX_QUERY_LEN",
    "SIMILARITY_THRESHOLD",
    "SearchResult",
    "normalize_query",
    "search_posts",
]
