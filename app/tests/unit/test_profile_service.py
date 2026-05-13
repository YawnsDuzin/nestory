"""Unit tests for app.services.profile — uses real DB session via factories."""
from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

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
