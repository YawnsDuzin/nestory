import factory
from factory.alchemy import SQLAlchemyModelFactory

from app.models import Journey
from app.models._enums import JourneyStatus
from app.tests.factories._session import _session_factory
from app.tests.factories.region import RegionFactory
from app.tests.factories.user import UserFactory


class JourneyFactory(SQLAlchemyModelFactory):
    class Meta:
        model = Journey
        sqlalchemy_session_factory = _session_factory
        sqlalchemy_session_persistence = "flush"

    title = factory.Sequence(lambda n: f"여정 {n}")
    status = JourneyStatus.IN_PROGRESS

    @factory.lazy_attribute
    def author_id(self):
        return UserFactory().id

    @factory.lazy_attribute
    def region_id(self):
        return RegionFactory().id
