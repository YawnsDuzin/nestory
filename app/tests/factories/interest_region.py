"""UserInterestRegion factory (composite PK on user_id + region_id)."""
import factory

from app.models import UserInterestRegion
from app.tests.factories._base import BaseFactory
from app.tests.factories.region import RegionFactory
from app.tests.factories.user import UserFactory


class UserInterestRegionFactory(BaseFactory):
    class Meta:
        model = UserInterestRegion
        exclude = ("user", "region")

    user = factory.SubFactory(UserFactory)
    user_id = factory.SelfAttribute("user.id")
    region = factory.SubFactory(RegionFactory)
    region_id = factory.SelfAttribute("region.id")

    priority = 1
