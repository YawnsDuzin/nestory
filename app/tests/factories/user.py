"""User factory and badge-level variants."""
from datetime import UTC, datetime, timedelta

import factory

from app.models import BadgeLevel, User, UserRole
from app.services.auth import hash_password
from app.tests.factories._base import BaseFactory


class UserFactory(BaseFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    username = factory.Sequence(lambda n: f"user{n}")
    display_name = factory.Faker("name", locale="ko_KR")
    password_hash = factory.LazyFunction(lambda: hash_password("test1234!"))
    role = UserRole.USER
    badge_level = BadgeLevel.INTERESTED


class AdminUserFactory(UserFactory):
    role = UserRole.ADMIN


class RegionVerifiedUserFactory(UserFactory):
    class Meta:
        model = User
        exclude = ("primary_region",)

    badge_level = BadgeLevel.REGION_VERIFIED
    primary_region = factory.SubFactory("app.tests.factories.region.RegionFactory")
    primary_region_id = factory.SelfAttribute("primary_region.id")


class ResidentUserFactory(RegionVerifiedUserFactory):
    class Meta:
        model = User
        exclude = ("primary_region",)

    badge_level = BadgeLevel.RESIDENT
    resident_verified_at = factory.LazyFunction(
        lambda: datetime.now(UTC) - timedelta(days=30)
    )
