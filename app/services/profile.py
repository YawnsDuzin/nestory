"""Profile service — public profile data + author posts/scraps + profile editing."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Image, Post, Region, User
from app.models._enums import PostStatus, PostType
from app.models.interaction import post_scraps
from app.services import auth

PAGE_SIZE = 20
USERNAME_CHANGE_THROTTLE_DAYS = 30
USERNAME_PATTERN = re.compile(r"^[a-z0-9_-]{3,32}$")
PASSWORD_MIN_LENGTH = 8
DISPLAY_NAME_MAX = 64
BIO_MAX = 500


class ProfileError(Exception):
    """Base exception for profile service errors."""


class UsernameTakenError(ProfileError):
    def __init__(self, username: str):
        self.username = username
        super().__init__(f"이미 사용 중인 사용자명입니다: {username}")


class UsernameThrottledError(ProfileError):
    """Username changed within last 30 days."""

    def __init__(self, days_remaining: int):
        self.days_remaining = days_remaining
        super().__init__(f"사용자명 변경은 {days_remaining}일 후 가능합니다")


class PasswordChangeNotAllowed(ProfileError):
    """Kakao OAuth users have no password to change."""

    def __init__(self):
        super().__init__("카카오 계정은 비밀번호 변경이 불가합니다")


class AvatarOwnershipError(ProfileError):
    """User attempted to set avatar to an Image they don't own."""

    def __init__(self):
        super().__init__("본인 소유 이미지가 아닙니다")


@dataclass
class ProfileData:
    user: User
    review_count: int
    journey_episode_count: int
    question_count: int


def get_by_username(db: Session, username: str) -> User | None:
    return db.scalar(
        select(User).where(User.username == username, User.deleted_at.is_(None))
    )


def profile_data(db: Session, user: User) -> ProfileData:
    base = select(func.count(Post.id)).where(
        Post.author_id == user.id,
        Post.status == PostStatus.PUBLISHED,
        Post.deleted_at.is_(None),
    )
    return ProfileData(
        user=user,
        review_count=db.scalar(base.where(Post.type == PostType.REVIEW)) or 0,
        journey_episode_count=db.scalar(base.where(Post.type == PostType.JOURNEY_EPISODE)) or 0,
        question_count=db.scalar(base.where(Post.type == PostType.QUESTION)) or 0,
    )


def author_posts(
    db: Session, user: User, post_type: PostType, *, page: int = 1
) -> tuple[list[Post], int]:
    base = (
        select(Post)
        .where(
            Post.author_id == user.id,
            Post.type == post_type,
            Post.status == PostStatus.PUBLISHED,
            Post.deleted_at.is_(None),
        )
        .options(selectinload(Post.region), selectinload(Post.author), selectinload(Post.journey))
    )
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    posts_stmt = (
        base.order_by(Post.published_at.desc())
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
    )
    posts = list(db.scalars(posts_stmt).all())
    return posts, total


def user_scraps(db: Session, user: User, *, page: int = 1) -> tuple[list[Post], int]:
    base = (
        select(Post)
        .join(post_scraps, post_scraps.c.post_id == Post.id)
        .where(
            post_scraps.c.user_id == user.id,
            Post.status == PostStatus.PUBLISHED,
            Post.deleted_at.is_(None),
        )
        .options(selectinload(Post.author), selectinload(Post.region), selectinload(Post.journey))
    )
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    posts_stmt = (
        base.order_by(post_scraps.c.created_at.desc())
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
    )
    posts = list(db.scalars(posts_stmt).all())
    return posts, total


def update_profile_basic(
    db: Session,
    user: User,
    *,
    display_name: str,
    bio: str | None,
    primary_region_id: int | None,
    notify_email_enabled: bool,
    notify_kakao_enabled: bool,
) -> User:
    """Update display_name/bio/region/notify settings. flush only — caller commits."""
    name = display_name.strip()
    if not name:
        raise ProfileError("표시 이름을 입력해 주세요")
    if len(name) > DISPLAY_NAME_MAX:
        raise ProfileError(f"표시 이름은 {DISPLAY_NAME_MAX}자 이하")

    bio_value: str | None = None
    if bio is not None:
        bio_stripped = bio.strip()
        if len(bio_stripped) > BIO_MAX:
            raise ProfileError(f"자기소개는 {BIO_MAX}자 이하")
        bio_value = bio_stripped or None  # 빈 문자열은 None으로 정규화

    region_id: int | None = None
    if primary_region_id is not None:
        region = db.get(Region, primary_region_id)
        if region is None:
            raise ProfileError("유효하지 않은 지역")
        region_id = region.id

    user.display_name = name
    user.bio = bio_value
    user.primary_region_id = region_id
    user.notify_email_enabled = bool(notify_email_enabled)
    user.notify_kakao_enabled = bool(notify_kakao_enabled)
    db.flush()
    return user


def set_avatar(db: Session, user: User, image: Image) -> User:
    """Set user.avatar_image_id. Raises AvatarOwnershipError if image.owner_id != user.id."""
    if image.owner_id != user.id:
        raise AvatarOwnershipError()
    user.avatar_image_id = image.id
    db.flush()
    return user


def clear_avatar(db: Session, user: User) -> User:
    """Set user.avatar_image_id to None. Old Image row is preserved (orphan GC = P2)."""
    user.avatar_image_id = None
    db.flush()
    return user


def change_username(db: Session, user: User, *, new_username: str) -> User:
    """Validate + apply new username.

    Raises UsernameThrottledError, UsernameTakenError, ProfileError.
    """
    normalized = new_username.strip().lower()
    if not USERNAME_PATTERN.fullmatch(normalized):
        raise ProfileError(
            "사용자명은 3-32자, 영소문자·숫자·_·- 만 사용할 수 있습니다"
        )
    if normalized == user.username:
        return user  # no-op — throttle 미적용
    if user.username_changed_at is not None:
        elapsed = (datetime.now(UTC) - user.username_changed_at).days
        if elapsed < USERNAME_CHANGE_THROTTLE_DAYS:
            raise UsernameThrottledError(USERNAME_CHANGE_THROTTLE_DAYS - elapsed)
    exists = db.scalar(select(User.id).where(User.username == normalized))
    if exists is not None:
        raise UsernameTakenError(normalized)
    user.username = normalized
    user.username_changed_at = datetime.now(UTC)
    db.flush()
    return user


def change_password(
    db: Session, user: User, *, current_password: str, new_password: str
) -> User:
    """Verify current + apply new hash. Raises PasswordChangeNotAllowed (kakao), ProfileError."""
    if user.password_hash is None:
        raise PasswordChangeNotAllowed()
    if not auth.verify_password(current_password, user.password_hash):
        raise ProfileError("현재 비밀번호가 일치하지 않습니다")
    if len(new_password) < PASSWORD_MIN_LENGTH:
        raise ProfileError(f"비밀번호는 최소 {PASSWORD_MIN_LENGTH}자 이상")
    user.password_hash = auth.hash_password(new_password)
    user.password_changed_at = datetime.now(UTC)
    db.flush()
    return user


__all__ = [
    "AvatarOwnershipError",
    "BIO_MAX",
    "DISPLAY_NAME_MAX",
    "PASSWORD_MIN_LENGTH",
    "PasswordChangeNotAllowed",
    "ProfileData",
    "ProfileError",
    "USERNAME_CHANGE_THROTTLE_DAYS",
    "USERNAME_PATTERN",
    "UsernameTakenError",
    "UsernameThrottledError",
    "PAGE_SIZE",
    "author_posts",
    "change_password",
    "change_username",
    "clear_avatar",
    "get_by_username",
    "profile_data",
    "set_avatar",
    "update_profile_basic",
    "user_scraps",
]
