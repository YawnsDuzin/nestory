"""Journey factory."""
import factory

from app.models import Journey
from app.models._enums import JourneyStatus
from app.tests.factories._base import BaseFactory
from app.tests.factories.region import RegionFactory
from app.tests.factories.user import UserFactory


class JourneyFactory(BaseFactory):
    class Meta:
        model = Journey
        exclude = ("author", "region")

    author = factory.SubFactory(UserFactory)
    author_id = factory.SelfAttribute("author.id")
    region = factory.SubFactory(RegionFactory)
    region_id = factory.SelfAttribute("region.id")

    title = factory.Faker("sentence", nb_words=3, locale="ko_KR")
    status = JourneyStatus.IN_PROGRESS
