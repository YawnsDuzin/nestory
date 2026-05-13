"""Feed service — home page data and global post feed."""
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from math import log10

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Post, Region, User, UserInterestRegion
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
    featured_testimonial: Post | None
    mixed_feed: list[Post]
    region_activity: list["RegionActivity"]


def home_data(db: Session, user: User | None) -> HomeData:
    """Return home page data: recommended regions, popular reviews, mixed feed."""
    # recommended_regions: 로그인 + UserInterestRegion 있으면 그 시군 우선,
    # 부족분은 기본 정렬로 보충
    interest_ids: list[int] = []
    if user is not None:
        interest_ids = list(
            db.scalars(
                select(UserInterestRegion.region_id)
                .where(UserInterestRegion.user_id == user.id)
                .order_by(UserInterestRegion.priority.asc(), UserInterestRegion.created_at.asc())
            ).all()
        )

    base_query = (
        select(Region)
        .order_by(Region.is_pilot.desc(), Region.id.asc())
    )
    if interest_ids:
        interest_regions = list(
            db.scalars(
                select(Region)
                .where(Region.id.in_(interest_ids))
            ).all()
        )
        # interest_ids 순서대로 재정렬
        order = {rid: i for i, rid in enumerate(interest_ids)}
        interest_regions.sort(key=lambda r: order[r.id])

        fill_count = max(0, 4 - len(interest_regions))
        fill_regions = list(
            db.scalars(
                base_query
                .where(Region.id.not_in(interest_ids))
                .limit(fill_count)
            ).all()
        ) if fill_count > 0 else []
        regions = interest_regions[:4] + fill_regions
    else:
        regions = list(db.scalars(base_query.limit(4)).all())

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

    mixed_feed = home_mixed_feed(db, user) if user is not None else []
    region_activity = region_activity_summary(db, regions) if user is not None else []

    return HomeData(
        recommended_regions=regions,
        popular_reviews=popular_reviews,
        featured_testimonial=popular_reviews[0] if popular_reviews else None,
        mixed_feed=mixed_feed,
        region_activity=region_activity,
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
            Post.type.in_([PostType.REVIEW, PostType.QUESTION]),
            Post.region_id.in_(region_ids),
            Post.status == PostStatus.PUBLISHED,
            Post.deleted_at.is_(None),
            Post.published_at >= cutoff,
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
        .options(selectinload(Post.author), selectinload(Post.region), selectinload(Post.journey))
    )
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    base = base.order_by(Post.published_at.desc()).offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)
    return list(db.scalars(base).all()), total


_FEED_WINDOW_DAYS = 14
_FEED_CANDIDATE_LIMIT = 30
_MAX_PER_TYPE = 3  # 같은 type이 3개 이상이면 페널티 적용


def _score_post(
    post: Post,
    *,
    now: datetime,
    followed_journey_ids: set[int],
    interest_region_ids: set[int],
    selected_type_counts: dict[PostType, int],
) -> float:
    """단일 post의 mixed feed 정렬용 score.

    base recency (0..1) + log popularity + follow boost + interest_region boost
    - diversity penalty (selected_type_counts >= _MAX_PER_TYPE 시).
    """
    days = (
        (now - post.published_at).total_seconds() / 86400
        if post.published_at
        else _FEED_WINDOW_DAYS
    )
    recency = max(0.0, (_FEED_WINDOW_DAYS - days) / _FEED_WINDOW_DAYS)  # 0..1
    popularity = min(0.6, log10(max(post.view_count, 0) + 1) * 0.3)
    follow = 0.5 if post.journey_id and post.journey_id in followed_journey_ids else 0.0
    interest = 0.3 if post.region_id in interest_region_ids else 0.0
    penalty = -0.2 if selected_type_counts.get(post.type, 0) >= _MAX_PER_TYPE else 0.0
    return recency + popularity + follow + interest + penalty


def home_mixed_feed(db: Session, user: User, *, limit: int = 8) -> list[Post]:
    """로그인 사용자의 "오늘의 발견" mixed feed 8개.

    Score 기반 정렬: recency + popularity + follow boost + interest_region boost
    - diversity penalty. 단일 query로 후보 30개를 가져온 뒤 Python에서 정렬.
    """
    cutoff = datetime.now(UTC) - timedelta(days=_FEED_WINDOW_DAYS)
    candidates = list(
        db.scalars(
            select(Post)
            .where(
                Post.type.in_([PostType.REVIEW, PostType.JOURNEY_EPISODE, PostType.QUESTION]),
                Post.status == PostStatus.PUBLISHED,
                Post.deleted_at.is_(None),
                Post.published_at >= cutoff,
            )
            .options(
                selectinload(Post.author),
                selectinload(Post.region),
                selectinload(Post.journey),
            )
            .order_by(Post.published_at.desc())
            .limit(_FEED_CANDIDATE_LIMIT)
        ).all()
    )
    if not candidates:
        return []

    followed_journey_ids: set[int] = set(
        db.scalars(
            select(journey_follows.c.journey_id).where(
                journey_follows.c.user_id == user.id
            )
        ).all()
    )
    interest_region_ids: set[int] = set(
        db.scalars(
            select(UserInterestRegion.region_id).where(
                UserInterestRegion.user_id == user.id
            )
        ).all()
    )

    now = datetime.now(UTC)
    selected: list[Post] = []
    selected_type_counts: dict[PostType, int] = {}
    remaining = list(candidates)

    while remaining and len(selected) < limit:
        # 매 라운드마다 (selected_type_counts 변동) score 재계산 후 best 선택
        scored = sorted(
            remaining,
            key=lambda p: _score_post(
                p, now=now,
                followed_journey_ids=followed_journey_ids,
                interest_region_ids=interest_region_ids,
                selected_type_counts=selected_type_counts,
            ),
            reverse=True,
        )
        pick = scored[0]
        selected.append(pick)
        selected_type_counts[pick.type] = selected_type_counts.get(pick.type, 0) + 1
        remaining.remove(pick)

    return selected


__all__ = [
    "PAGE_SIZE",
    "HomeData",
    "RegionActivity",
    "home_data",
    "home_mixed_feed",
    "region_activity_summary",
    "global_feed",
]
