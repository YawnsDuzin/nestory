"""Hub service — region overview, tab posts, and neighbor residents."""
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Post, Region, User
from app.models._enums import BadgeLevel, PostStatus, PostType

PAGE_SIZE = 20

_RESIDENT_LEVELS = [BadgeLevel.RESIDENT, BadgeLevel.EX_RESIDENT]


@dataclass
class HubOverview:
    region: Region
    review_count: int
    journey_count: int
    question_count: int
    resident_count: int
    popular_reviews: list[Post]
    recent_journeys: list[Post]
    recent_questions: list[Post]


def get_region_by_slug(db: Session, slug: str) -> Region | None:
    """Return the Region with the given slug, or None if not found."""
    return db.scalar(select(Region).where(Region.slug == slug))


def hub_overview(db: Session, region: Region) -> HubOverview:
    """Return counts and top posts for the given region hub page."""
    base_count = select(func.count(Post.id)).where(
        Post.region_id == region.id,
        Post.status == PostStatus.PUBLISHED,
        Post.deleted_at.is_(None),
    )
    review_count = (
        db.scalar(base_count.where(Post.type == PostType.REVIEW)) or 0
    )
    journey_count = (
        db.scalar(base_count.where(Post.type == PostType.JOURNEY_EPISODE)) or 0
    )
    question_count = (
        db.scalar(base_count.where(Post.type == PostType.QUESTION)) or 0
    )
    resident_count = (
        db.scalar(
            select(func.count(User.id)).where(
                User.primary_region_id == region.id,
                User.badge_level.in_(_RESIDENT_LEVELS),
            )
        )
        or 0
    )

    def _top(post_type: PostType, by: Literal["view", "latest"] = "view") -> list[Post]:
        stmt = (
            select(Post)
            .where(
                Post.region_id == region.id,
                Post.type == post_type,
                Post.status == PostStatus.PUBLISHED,
                Post.deleted_at.is_(None),
            )
            .options(selectinload(Post.author), selectinload(Post.region))
            .limit(4)
        )
        if by == "view":
            stmt = stmt.order_by(Post.view_count.desc(), Post.published_at.desc())
        else:
            stmt = stmt.order_by(Post.published_at.desc())
        return list(db.scalars(stmt).all())

    return HubOverview(
        region=region,
        review_count=review_count,
        journey_count=journey_count,
        question_count=question_count,
        resident_count=resident_count,
        popular_reviews=_top(PostType.REVIEW, by="view"),
        recent_journeys=_top(PostType.JOURNEY_EPISODE, by="latest"),
        recent_questions=_top(PostType.QUESTION, by="latest"),
    )


def hub_tab_posts(
    db: Session,
    region: Region,
    post_type: PostType,
    *,
    sort: Literal["latest", "popular"] = "latest",
    page: int = 1,
) -> tuple[list[Post], int]:
    """Return paginated posts for a hub tab (one PostType, one Region)."""
    base = (
        select(Post)
        .where(
            Post.region_id == region.id,
            Post.type == post_type,
            Post.status == PostStatus.PUBLISHED,
            Post.deleted_at.is_(None),
        )
        .options(selectinload(Post.author), selectinload(Post.region))
    )
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    if sort == "popular":
        base = base.order_by(Post.view_count.desc(), Post.published_at.desc())
    else:
        base = base.order_by(Post.published_at.desc())
    base = base.offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)
    return list(db.scalars(base).all()), total


def region_neighbors(db: Session, region: Region) -> list[User]:
    """Return RESIDENT and EX_RESIDENT users for a region, capped at 50."""
    stmt = (
        select(User)
        .where(
            User.primary_region_id == region.id,
            User.badge_level.in_(_RESIDENT_LEVELS),
        )
        .order_by(User.resident_verified_at.desc().nulls_last(), User.username.asc())
        .limit(50)
    )
    return list(db.scalars(stmt).all())


__all__ = [
    "PAGE_SIZE",
    "HubOverview",
    "get_region_by_slug",
    "hub_overview",
    "hub_tab_posts",
    "region_neighbors",
]
