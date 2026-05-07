"""Region factory with get-or-create on slug."""
import factory

from app.models import Region
from app.tests.factories._base import BaseFactory


class RegionFactory(BaseFactory):
    class Meta:
        model = Region
        sqlalchemy_get_or_create = ("slug",)

    sido = "경기"
    sigungu = factory.Sequence(lambda n: f"테스트시{n}")
    slug = factory.Sequence(lambda n: f"test-{n}")
    is_pilot = False


class PilotRegionFactory(RegionFactory):
    is_pilot = True
