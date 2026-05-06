"""factory-boy factories for integration tests.

Bind a SQLAlchemy session via `bind_session(db)` from a pytest fixture
before using any factory. The conftest._bind_factories autouse fixture
handles this automatically.
"""
from app.tests.factories._session import bind_session
from app.tests.factories.image import ImageFactory
from app.tests.factories.journey import JourneyFactory
from app.tests.factories.post import (
    AnswerPostFactory,
    JourneyEpisodePostFactory,
    PlanPostFactory,
    PostFactory,
    QuestionPostFactory,
    ReviewPostFactory,
)
from app.tests.factories.region import RegionFactory
from app.tests.factories.user import UserFactory

__all__ = [
    "AnswerPostFactory",
    "ImageFactory",
    "JourneyEpisodePostFactory",
    "JourneyFactory",
    "PlanPostFactory",
    "PostFactory",
    "QuestionPostFactory",
    "RegionFactory",
    "ReviewPostFactory",
    "UserFactory",
    "bind_session",
]
