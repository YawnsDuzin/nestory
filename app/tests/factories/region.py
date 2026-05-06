import factory
from factory.alchemy import SQLAlchemyModelFactory

from app.models import Region
from app.tests.factories._session import _session_factory


class RegionFactory(SQLAlchemyModelFactory):
    class Meta:
        model = Region
        sqlalchemy_session_factory = _session_factory
        sqlalchemy_session_persistence = "flush"

    sido = "경기도"
    sigungu = "양평군"
    slug = factory.Sequence(lambda n: f"region-{n}")
    is_pilot = False
