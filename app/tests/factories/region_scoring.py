"""RegionScoringWeight factory."""
import factory

from app.models import RegionScoringWeight
from app.tests.factories._base import BaseFactory
from app.tests.factories.region import RegionFactory


class RegionScoringWeightFactory(BaseFactory):
    class Meta:
        model = RegionScoringWeight
        exclude = ("region",)

    region = factory.SubFactory(RegionFactory)
    region_id = factory.SelfAttribute("region.id")

    activity_score = 5
    medical_score = 5
    family_visit_score = 5
    farming_score = 5
    budget_score = 5
    notes = None
