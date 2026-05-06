import factory
from factory.alchemy import SQLAlchemyModelFactory

from app.models import Post
from app.models._enums import PostStatus, PostType
from app.tests.factories._session import _session_factory
from app.tests.factories.region import RegionFactory
from app.tests.factories.user import UserFactory


class PostFactory(SQLAlchemyModelFactory):
    class Meta:
        model = Post
        sqlalchemy_session_factory = _session_factory
        sqlalchemy_session_persistence = "flush"

    type = PostType.REVIEW
    title = factory.Sequence(lambda n: f"제목 {n}")
    body = "본문"
    status = PostStatus.DRAFT
    metadata_ = factory.LazyFunction(dict)

    @factory.lazy_attribute
    def author_id(self):
        return UserFactory().id

    @factory.lazy_attribute
    def region_id(self):
        return RegionFactory().id


class ReviewPostFactory(PostFactory):
    type = PostType.REVIEW


class JourneyEpisodePostFactory(PostFactory):
    type = PostType.JOURNEY_EPISODE


class QuestionPostFactory(PostFactory):
    type = PostType.QUESTION


class AnswerPostFactory(PostFactory):
    type = PostType.ANSWER


class PlanPostFactory(PostFactory):
    type = PostType.PLAN
