from app.tests.factories.badge_application import (
    BadgeApplicationFactory,
    BadgeEvidenceFactory,
)
from app.tests.factories.comment import CommentFactory
from app.tests.factories.image import ImageFactory
from app.tests.factories.interaction import (  # noqa: F401  # helper functions
    add_journey_follow,
    add_post_like,
    add_post_scrap,
    add_user_follow,
)
from app.tests.factories.interest_region import UserInterestRegionFactory
from app.tests.factories.job import JobFactory
from app.tests.factories.journey import JourneyFactory
from app.tests.factories.moderation import (
    AnnouncementFactory,
    AuditLogFactory,
    ReportFactory,
)
from app.tests.factories.notification import NotificationFactory
from app.tests.factories.post import (
    AnswerPostFactory,
    JourneyEpisodePostFactory,
    PlanPostFactory,
    PostFactory,
    QuestionPostFactory,
    ReviewPostFactory,
)
from app.tests.factories.post_validation import PostValidationFactory
from app.tests.factories.region import PilotRegionFactory, RegionFactory
from app.tests.factories.tag import TagFactory
from app.tests.factories.user import (
    AdminUserFactory,
    RegionVerifiedUserFactory,
    ResidentUserFactory,
    UserFactory,
)

__all__ = [
    "AdminUserFactory",
    "AnnouncementFactory",
    "AnswerPostFactory",
    "AuditLogFactory",
    "BadgeApplicationFactory",
    "BadgeEvidenceFactory",
    "CommentFactory",
    "ImageFactory",
    "JobFactory",
    "JourneyEpisodePostFactory",
    "JourneyFactory",
    "NotificationFactory",
    "PilotRegionFactory",
    "PlanPostFactory",
    "PostFactory",
    "PostValidationFactory",
    "QuestionPostFactory",
    "RegionFactory",
    "RegionVerifiedUserFactory",
    "ReportFactory",
    "ResidentUserFactory",
    "ReviewPostFactory",
    "TagFactory",
    "UserFactory",
    "UserInterestRegionFactory",
    "add_journey_follow",
    "add_post_like",
    "add_post_scrap",
    "add_user_follow",
]
