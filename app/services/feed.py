"""Feed service — home page data and global post feed."""
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Post, Region, User
from app.models._enums import PostStatus, PostType
from app.models.interaction import journey_follows

PAGE_SIZE = 20


@dataclass
class RegionActivity:
    region: Region
    new_reviews_7d: int
    new_questions_7d: int


@dataclass
class HomeData:
    recommended_regions: list[Region]
    popular_reviews: list[Post]
    recent_journeys: list[Post]
    followed_episodes: list[Post]
    featured_testimonial: Post | None


def home_data(db: Session, user: User | None) -> HomeData:
    """Return home page data: recommended regions, popular/recent posts, followed episodes."""
    regions = list(
        db.scalars(
            select(Region)
            .order_by(Region.is_pilot.desc(), Region.id.asc())
            .limit(4)
        ).all()
    )

    popular_reviews = list(
        db.scalars(
            select(Post)
            .where(
                Post.type == PostType.REVIEW,
                Post.status == PostStatus.PUBLISHED,
                Post.deleted_at.is_(None),
            )
            .options(selectinload(Post.author), selectinload(Post.region))
            .order_by(Post.view_count.desc(), Post.published_at.desc())
            .limit(4)
        ).all()
    )

    recent_journeys = list(
        db.scalars(
            select(Post)
            .where(
                Post.type == PostType.JOURNEY_EPISODE,
                Post.status == PostStatus.PUBLISHED,
                Post.deleted_at.is_(None),
            )
            .options(selectinload(Post.author), selectinload(Post.region))
            .order_by(Post.published_at.desc())
            .limit(4)
        ).all()
    )

    followed_episodes: list[Post] = []
    if user is not None:
        followed_episodes = list(
            db.scalars(
                select(Post)
                .join(
                    journey_follows,
                    journey_follows.c.journey_id == Post.journey_id,
                )
                .where(
                    journey_follows.c.user_id == user.id,
                    Post.type == PostType.JOURNEY_EPISODE,
                    Post.status == PostStatus.PUBLISHED,
                    Post.deleted_at.is_(None),
                )
                .options(selectinload(Post.author), selectinload(Post.region))
                .order_by(Post.published_at.desc())
                .limit(8)
            ).all()
        )

    return HomeData(
        recommended_regions=regions,
        popular_reviews=popular_reviews,
        recent_journeys=recent_journeys,
        followed_episodes=followed_episodes,
        featured_testimonial=popular_reviews[0] if popular_reviews else None,
    )


def region_activity_summary(db: Session, regions: list[Region]) -> list[RegionActivity]:
    """주어진 시군들의 최근 7일 published review·question 카운터를 반환.

    입력 순서를 보존한다. 단일 GROUP BY 쿼리 — N+1 없음.
    """
    if not regions:
        return []
    region_ids = [r.id for r in regions]
    cutoff = datetime.now(UTC) - timedelta(days=7)

    rows = db.execute(
        select(Post.region_id, Post.type, func.count().label("cnt"))
        .where(
            Post.region_id.in_(region_ids),
            Post.status == PostStatus.PUBLISHED,
            Post.deleted_at.is_(None),
            Post.published_at >= cutoff,
            Post.type.in_([PostType.REVIEW, PostType.QUESTION]),
        )
        .group_by(Post.region_id, Post.type)
    ).all()

    # (region_id, type) → count
    counts: dict[tuple[int, PostType], int] = {
        (r.region_id, r.type): r.cnt for r in rows
    }
    return [
        RegionActivity(
            region=region,
            new_reviews_7d=counts.get((region.id, PostType.REVIEW), 0),
            new_questions_7d=counts.get((region.id, PostType.QUESTION), 0),
        )
        for region in regions
    ]


def global_feed(db: Session, *, page: int = 1) -> tuple[list[Post], int]:
    """Return all published posts ordered by published_at DESC, paginated."""
    base = (
        select(Post)
        .where(
            Post.status == PostStatus.PUBLISHED,
            Post.deleted_at.is_(None),
        )
        .options(selectinload(Post.author), selectinload(Post.region))
    )
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    base = base.order_by(Post.published_at.desc()).offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)
    return list(db.scalars(base).all()), total


__all__ = [
    "PAGE_SIZE",
    "HomeData",
    "RegionActivity",
    "home_data",
    "region_activity_summary",
    "global_feed",
]
