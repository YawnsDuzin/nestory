"""BadgeApplication and BadgeEvidence factories."""
import factory

from app.models import BadgeApplication, BadgeEvidence
from app.models._enums import (
    BadgeApplicationStatus,
    BadgeRequestedLevel,
    EvidenceType,
)
from app.tests.factories._base import BaseFactory
from app.tests.factories.region import RegionFactory
from app.tests.factories.user import UserFactory


class BadgeApplicationFactory(BaseFactory):
    class Meta:
        model = BadgeApplication
        exclude = ("user", "region")

    user = factory.SubFactory(UserFactory)
    user_id = factory.SelfAttribute("user.id")
    region = factory.SubFactory(RegionFactory)
    region_id = factory.SelfAttribute("region.id")

    requested_level = BadgeRequestedLevel.REGION_VERIFIED
    status = BadgeApplicationStatus.PENDING


class BadgeEvidenceFactory(BaseFactory):
    class Meta:
        model = BadgeEvidence
        exclude = ("application",)

    application = factory.SubFactory(BadgeApplicationFactory)
    application_id = factory.SelfAttribute("application.id")

    evidence_type = EvidenceType.UTILITY_BILL
    file_path = factory.Sequence(lambda n: f"evidence/{n}/test.jpg")
