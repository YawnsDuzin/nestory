"""Sanity tests for every factory. Each factory should produce a persisted row
and (where applicable) a Pydantic-valid metadata payload."""
from sqlalchemy.orm import Session

from app.models import BadgeLevel, Region, UserRole


def test_user_factory_creates_user(db: Session) -> None:
    from app.tests.factories import UserFactory

    user = UserFactory()
    assert user.id is not None
    assert user.email.endswith("@example.com")
    assert user.role == UserRole.USER
    assert user.badge_level == BadgeLevel.INTERESTED
    # password_hash must be a real argon2 hash, not plaintext
    assert user.password_hash and user.password_hash.startswith("$argon2")


def test_admin_user_factory(db: Session) -> None:
    from app.tests.factories import AdminUserFactory

    admin = AdminUserFactory()
    assert admin.role == UserRole.ADMIN


def test_region_factory_creates_region(db: Session) -> None:
    from app.tests.factories import RegionFactory

    r = RegionFactory()
    assert r.id is not None
    assert r.sido == "경기"
    assert r.slug.startswith("test-")


def test_region_factory_get_or_create(db: Session) -> None:
    from app.tests.factories import RegionFactory

    r1 = RegionFactory(slug="dup-slug")
    r2 = RegionFactory(slug="dup-slug")
    assert r1.id == r2.id


def test_region_verified_user_factory_has_primary_region(db: Session) -> None:
    from app.tests.factories import RegionVerifiedUserFactory

    u = RegionVerifiedUserFactory()
    assert u.badge_level == BadgeLevel.REGION_VERIFIED
    assert u.primary_region_id is not None
    region = db.query(Region).filter_by(id=u.primary_region_id).one()
    assert region is not None


def test_resident_user_factory(db: Session) -> None:
    from app.tests.factories import ResidentUserFactory

    u = ResidentUserFactory()
    assert u.badge_level == BadgeLevel.RESIDENT
    assert u.resident_verified_at is not None
