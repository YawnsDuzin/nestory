"""Integration tests for profile service.

Covers:
- get_by_username: found, not found, soft-deleted
- profile_data: count by type, excludes other users, zero counts
- author_posts: type filter, author isolation, draft exclusion, ordering, pagination
- user_scraps: ordering, user isolation, draft/deleted exclusion

NOTE: These tests require a running Postgres instance.
      They CANNOT be executed on a no-Docker PC — run on docker-up PC.
"""
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models._enums import PostStatus, PostType
from app.services import profile as profile_service
from app.tests.factories import (
    JourneyEpisodePostFactory,
    QuestionPostFactory,
    RegionFactory,
    ReviewPostFactory,
    UserFactory,
    add_post_scrap,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _published_review(region, author, *, published_at=None, **kwargs):
    """Shorthand: PUBLISHED ReviewPost with explicit author."""
    return ReviewPostFactory(
        author=author,
        region=region,
        status=PostStatus.PUBLISHED,
        published_at=published_at or datetime.now(UTC),
        **kwargs,
    )


def _published_question(region, author, **kwargs):
    return QuestionPostFactory(
        author=author,
        region=region,
        status=PostStatus.PUBLISHED,
        published_at=datetime.now(UTC),
        **kwargs,
    )


def _published_episode(region, author, **kwargs):
    return JourneyEpisodePostFactory(
        author=author,
        region=region,
        status=PostStatus.PUBLISHED,
        published_at=datetime.now(UTC),
        **kwargs,
    )


# ---------------------------------------------------------------------------
# 1. get_by_username — known username
# ---------------------------------------------------------------------------


def test_get_by_username_returns_user(db: Session) -> None:
    user = UserFactory(username="profile-known-user")
    db.flush()

    result = profile_service.get_by_username(db, "profile-known-user")
    assert result is not None
    assert result.id == user.id


# ---------------------------------------------------------------------------
# 2. get_by_username — unknown returns None
# ---------------------------------------------------------------------------


def test_get_by_username_unknown_returns_none(db: Session) -> None:
    result = profile_service.get_by_username(db, "profile-no-such-user-xyz")
    assert result is None


# ---------------------------------------------------------------------------
# 3. get_by_username — excludes soft-deleted
# ---------------------------------------------------------------------------


def test_get_by_username_excludes_soft_deleted(db: Session) -> None:
    UserFactory(username="profile-deleted-user", deleted_at=datetime.now(UTC))
    db.flush()

    result = profile_service.get_by_username(db, "profile-deleted-user")
    assert result is None


# ---------------------------------------------------------------------------
# 4. profile_data — counts published posts by type; DRAFT not counted;
#    ANSWER/PLAN do not appear in the 3 exposed fields
# ---------------------------------------------------------------------------


def test_profile_data_counts_published_posts_by_type(db: Session) -> None:
    region = RegionFactory(slug="profile-counts-region")
    user = UserFactory()

    _published_review(region, user)
    _published_review(region, user)
    _published_episode(region, user)
    _published_question(region, user)

    # DRAFT should NOT be counted
    ReviewPostFactory(author=user, region=region, status=PostStatus.DRAFT)
    db.flush()

    data = profile_service.profile_data(db, user)
    assert data.user is user
    assert data.review_count == 2
    assert data.journey_episode_count == 1
    assert data.question_count == 1


# ---------------------------------------------------------------------------
# 5. profile_data — excludes other user posts
# ---------------------------------------------------------------------------


def test_profile_data_excludes_other_user_posts(db: Session) -> None:
    region = RegionFactory(slug="profile-other-user-region")
    user = UserFactory()
    other = UserFactory()

    _published_review(region, user)
    _published_review(region, other)
    db.flush()

    data = profile_service.profile_data(db, user)
    assert data.review_count == 1


# ---------------------------------------------------------------------------
# 6. profile_data — zero counts for new user
# ---------------------------------------------------------------------------


def test_profile_data_zero_counts_for_new_user(db: Session) -> None:
    user = UserFactory()
    db.flush()

    data = profile_service.profile_data(db, user)
    assert data.review_count == 0
    assert data.journey_episode_count == 0
    assert data.question_count == 0


# ---------------------------------------------------------------------------
# 7. author_posts — returns only specified type
# ---------------------------------------------------------------------------


def test_author_posts_returns_only_specified_type(db: Session) -> None:
    region = RegionFactory(slug="profile-type-filter-region")
    user = UserFactory()

    review = _published_review(region, user)
    _published_question(region, user)
    db.flush()

    posts = profile_service.author_posts(db, user, PostType.REVIEW)
    ids = [p.id for p in posts]
    assert review.id in ids
    for p in posts:
        assert p.type == PostType.REVIEW


# ---------------------------------------------------------------------------
# 8. author_posts — excludes other authors
# ---------------------------------------------------------------------------


def test_author_posts_excludes_other_authors(db: Session) -> None:
    region = RegionFactory(slug="profile-author-isolation-region")
    user = UserFactory()
    other = UserFactory()

    _published_review(region, user)
    other_post = _published_review(region, other)
    db.flush()

    posts = profile_service.author_posts(db, user, PostType.REVIEW)
    ids = [p.id for p in posts]
    assert other_post.id not in ids


# ---------------------------------------------------------------------------
# 9. author_posts — excludes drafts
# ---------------------------------------------------------------------------


def test_author_posts_excludes_drafts(db: Session) -> None:
    region = RegionFactory(slug="profile-drafts-region")
    user = UserFactory()

    published = _published_review(region, user)
    ReviewPostFactory(author=user, region=region, status=PostStatus.DRAFT)
    db.flush()

    posts = profile_service.author_posts(db, user, PostType.REVIEW)
    ids = [p.id for p in posts]
    assert published.id in ids
    for p in posts:
        assert p.status == PostStatus.PUBLISHED


# ---------------------------------------------------------------------------
# 10. author_posts — orders by published_at DESC
# ---------------------------------------------------------------------------


def test_author_posts_orders_by_published_at_desc(db: Session) -> None:
    region = RegionFactory(slug="profile-order-region")
    user = UserFactory()

    older = _published_review(region, user, published_at=datetime(2025, 1, 1, tzinfo=UTC))
    newer = _published_review(region, user, published_at=datetime(2026, 6, 1, tzinfo=UTC))
    db.flush()

    posts = profile_service.author_posts(db, user, PostType.REVIEW)
    ids = [p.id for p in posts]
    assert newer.id in ids
    assert older.id in ids
    assert ids.index(newer.id) < ids.index(older.id)


# ---------------------------------------------------------------------------
# 11. author_posts — pagination: 22 posts → page 1 = 20, page 2 = 2
# ---------------------------------------------------------------------------


def test_author_posts_pagination(db: Session) -> None:
    region = RegionFactory(slug="profile-pagination-region")
    user = UserFactory()

    for _ in range(22):
        _published_review(region, user)
    db.flush()

    page1 = profile_service.author_posts(db, user, PostType.REVIEW, page=1)
    page2 = profile_service.author_posts(db, user, PostType.REVIEW, page=2)

    assert len(page1) == profile_service.PAGE_SIZE
    assert len(page2) == 2

    p1_ids = {p.id for p in page1}
    p2_ids = {p.id for p in page2}
    assert p1_ids.isdisjoint(p2_ids)


# ---------------------------------------------------------------------------
# 12. user_scraps — orders by scrap created_at DESC
# ---------------------------------------------------------------------------


def test_user_scraps_orders_by_scrap_created_at_desc(db: Session) -> None:
    """Scrap A added first, scrap B added later; result[0] must be B."""
    region = RegionFactory(slug="profile-scraps-order-region")
    user = UserFactory()
    author = UserFactory()

    post_a = _published_review(region, author)
    post_b = _published_review(region, author)
    db.flush()

    # Insert scraps with explicit timestamps to control ordering
    from app.models.interaction import post_scraps as _post_scraps

    db.execute(
        _post_scraps.insert().values(
            user_id=user.id,
            post_id=post_a.id,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    db.execute(
        _post_scraps.insert().values(
            user_id=user.id,
            post_id=post_b.id,
            created_at=datetime(2026, 6, 1, tzinfo=UTC),
        )
    )
    db.flush()

    scraps = profile_service.user_scraps(db, user)
    ids = [p.id for p in scraps]
    assert post_b.id in ids
    assert post_a.id in ids
    assert ids.index(post_b.id) < ids.index(post_a.id)


# ---------------------------------------------------------------------------
# 13. user_scraps — isolates users
# ---------------------------------------------------------------------------


def test_user_scraps_isolates_users(db: Session) -> None:
    """userA scraps post1; userB.user_scraps must not contain post1."""
    region = RegionFactory(slug="profile-scraps-isolation-region")
    user_a = UserFactory()
    user_b = UserFactory()
    author = UserFactory()

    post1 = _published_review(region, author)
    db.flush()

    add_post_scrap(db, user_a, post1)
    db.flush()

    scraps_b = profile_service.user_scraps(db, user_b)
    ids_b = [p.id for p in scraps_b]
    assert post1.id not in ids_b


# ---------------------------------------------------------------------------
# 14. user_scraps — excludes drafts and soft-deleted
# ---------------------------------------------------------------------------


def test_user_scraps_excludes_drafts_and_deleted(db: Session) -> None:
    """Scrapping a DRAFT post or a soft-deleted post must not appear in results."""
    region = RegionFactory(slug="profile-scraps-excl-region")
    user = UserFactory()
    author = UserFactory()

    published = _published_review(region, author)
    draft_post = ReviewPostFactory(author=author, region=region, status=PostStatus.DRAFT)
    deleted_post = ReviewPostFactory(
        author=author,
        region=region,
        status=PostStatus.PUBLISHED,
        published_at=datetime.now(UTC),
        deleted_at=datetime.now(UTC),
    )
    db.flush()

    add_post_scrap(db, user, published)
    add_post_scrap(db, user, draft_post)
    add_post_scrap(db, user, deleted_post)
    db.flush()

    scraps = profile_service.user_scraps(db, user)
    ids = [p.id for p in scraps]
    assert published.id in ids
    assert draft_post.id not in ids
    assert deleted_post.id not in ids
