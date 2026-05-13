"""Unit tests for app.services.profile — uses real DB session via factories."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.services import auth as auth_service
from app.services import profile
from app.tests.factories import RegionFactory, UserFactory


def test_update_profile_basic_happy(db: Session) -> None:
    region = RegionFactory(slug="profile-basic-region")
    user = UserFactory(display_name="원래이름", bio=None)
    db.flush()

    updated = profile.update_profile_basic(
        db, user,
        display_name="  새 이름  ",  # trimmed
        bio="자기소개입니다",
        primary_region_id=region.id,
        notify_email_enabled=False,
        notify_kakao_enabled=True,
    )

    assert updated.display_name == "새 이름"
    assert updated.bio == "자기소개입니다"
    assert updated.primary_region_id == region.id
    assert updated.notify_email_enabled is False
    assert updated.notify_kakao_enabled is True


def test_update_profile_basic_allows_none_bio_and_region(db: Session) -> None:
    user = UserFactory(display_name="초기이름")
    db.flush()
    updated = profile.update_profile_basic(
        db, user,
        display_name="이름",
        bio=None,
        primary_region_id=None,
        notify_email_enabled=True,
        notify_kakao_enabled=False,
    )
    assert updated.bio is None
    assert updated.primary_region_id is None


def test_update_profile_basic_rejects_blank_display_name(db: Session) -> None:
    user = UserFactory(display_name="기존")
    db.flush()
    with pytest.raises(profile.ProfileError):
        profile.update_profile_basic(
            db, user,
            display_name="   ",
            bio=None,
            primary_region_id=None,
            notify_email_enabled=True,
            notify_kakao_enabled=False,
        )


def test_update_profile_basic_rejects_too_long_display_name(db: Session) -> None:
    user = UserFactory()
    db.flush()
    with pytest.raises(profile.ProfileError):
        profile.update_profile_basic(
            db, user,
            display_name="가" * 65,  # > DISPLAY_NAME_MAX (64)
            bio=None,
            primary_region_id=None,
            notify_email_enabled=True,
            notify_kakao_enabled=False,
        )


def test_update_profile_basic_rejects_too_long_bio(db: Session) -> None:
    user = UserFactory()
    db.flush()
    with pytest.raises(profile.ProfileError):
        profile.update_profile_basic(
            db, user,
            display_name="이름",
            bio="가" * 501,  # > BIO_MAX (500)
            primary_region_id=None,
            notify_email_enabled=True,
            notify_kakao_enabled=False,
        )


def test_update_profile_basic_rejects_invalid_region(db: Session) -> None:
    user = UserFactory()
    db.flush()
    with pytest.raises(profile.ProfileError):
        profile.update_profile_basic(
            db, user,
            display_name="이름",
            bio=None,
            primary_region_id=999_999,  # 존재하지 않는 region
            notify_email_enabled=True,
            notify_kakao_enabled=False,
        )


def test_set_avatar_happy(db: Session) -> None:
    from app.tests.factories import ImageFactory

    user = UserFactory()
    image = ImageFactory(owner=user)
    db.flush()

    updated = profile.set_avatar(db, user, image)
    assert updated.avatar_image_id == image.id


def test_set_avatar_rejects_other_users_image(db: Session) -> None:
    from app.tests.factories import ImageFactory

    owner = UserFactory()
    intruder = UserFactory()
    image = ImageFactory(owner=owner)
    db.flush()

    with pytest.raises(profile.AvatarOwnershipError):
        profile.set_avatar(db, intruder, image)


def test_clear_avatar_when_set(db: Session) -> None:
    from app.tests.factories import ImageFactory

    user = UserFactory()
    image = ImageFactory(owner=user)
    db.flush()
    user.avatar_image_id = image.id
    db.flush()

    updated = profile.clear_avatar(db, user)
    assert updated.avatar_image_id is None


def test_clear_avatar_when_already_none(db: Session) -> None:
    user = UserFactory()
    db.flush()
    updated = profile.clear_avatar(db, user)
    assert updated.avatar_image_id is None


def test_change_username_happy(db: Session) -> None:
    user = UserFactory(username="oldname")
    db.flush()
    before = datetime.now(UTC)
    updated = profile.change_username(db, user, new_username="newname")
    assert updated.username == "newname"
    assert updated.username_changed_at is not None
    assert updated.username_changed_at >= before


def test_change_username_normalizes_to_lowercase(db: Session) -> None:
    user = UserFactory(username="oldname")
    db.flush()
    updated = profile.change_username(db, user, new_username="  NewName  ")
    assert updated.username == "newname"


def test_change_username_no_op_when_same(db: Session) -> None:
    """Same username (after normalization) — no-op, no throttle update."""
    user = UserFactory(username="samename", username_changed_at=None)
    db.flush()
    updated = profile.change_username(db, user, new_username="SameName")
    assert updated.username == "samename"
    assert updated.username_changed_at is None  # not touched


def test_change_username_rejects_invalid_pattern(db: Session) -> None:
    user = UserFactory()
    db.flush()
    for bad in ("ab", "with spaces", "한글이름", "a" * 33):
        with pytest.raises(profile.ProfileError):
            profile.change_username(db, user, new_username=bad)


def test_change_username_rejects_duplicate(db: Session) -> None:
    UserFactory(username="taken")
    user = UserFactory(username="mine")
    db.flush()
    with pytest.raises(profile.UsernameTakenError):
        profile.change_username(db, user, new_username="taken")


def test_change_username_within_throttle_window_rejected(db: Session) -> None:
    user = UserFactory(
        username="oldname",
        username_changed_at=datetime.now(UTC) - timedelta(days=10),
    )
    db.flush()
    with pytest.raises(profile.UsernameThrottledError) as exc_info:
        profile.change_username(db, user, new_username="newname")
    # 30 - 10 = 20 days remaining (allow ±1 day for test execution drift)
    assert 19 <= exc_info.value.days_remaining <= 21


def test_change_username_after_throttle_window_allowed(db: Session) -> None:
    user = UserFactory(
        username="oldname",
        username_changed_at=datetime.now(UTC) - timedelta(days=31),
    )
    db.flush()
    updated = profile.change_username(db, user, new_username="newname")
    assert updated.username == "newname"


def test_change_password_happy(db: Session) -> None:
    user = UserFactory(password_hash=auth_service.hash_password("oldPassword!"))
    db.flush()
    updated = profile.change_password(
        db, user,
        current_password="oldPassword!",
        new_password="newPassword!",
    )
    assert auth_service.verify_password("newPassword!", updated.password_hash) is True
    assert auth_service.verify_password("oldPassword!", updated.password_hash) is False


def test_change_password_rejects_kakao_user(db: Session) -> None:
    """Kakao OAuth user has password_hash=None — change must be denied."""
    user = UserFactory(password_hash=None, kakao_id="kakao_abc123")
    db.flush()
    with pytest.raises(profile.PasswordChangeNotAllowed):
        profile.change_password(
            db, user,
            current_password="anything",
            new_password="newPassword!",
        )


def test_change_password_rejects_wrong_current(db: Session) -> None:
    user = UserFactory(password_hash=auth_service.hash_password("realPassword"))
    db.flush()
    with pytest.raises(profile.ProfileError):
        profile.change_password(
            db, user,
            current_password="wrongPassword",
            new_password="newPassword!",
        )


def test_change_password_rejects_short_new(db: Session) -> None:
    user = UserFactory(password_hash=auth_service.hash_password("realPassword"))
    db.flush()
    with pytest.raises(profile.ProfileError):
        profile.change_password(
            db, user,
            current_password="realPassword",
            new_password="short",  # < PASSWORD_MIN_LENGTH (8)
        )
