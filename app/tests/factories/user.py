import factory
from factory.alchemy import SQLAlchemyModelFactory

from app.models import User
from app.models.user import BadgeLevel, UserRole
from app.tests.factories._session import _session_factory


class UserFactory(SQLAlchemyModelFactory):
    class Meta:
        model = User
        sqlalchemy_session_factory = _session_factory
        sqlalchemy_session_persistence = "flush"

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    username = factory.Sequence(lambda n: f"user{n}")
    display_name = "테스터"
    password_hash = "x"
    role = UserRole.USER
    badge_level = BadgeLevel.INTERESTED
