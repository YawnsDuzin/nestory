"""Post factory with type-aware metadata defaults."""
import factory

from app.models import Post
from app.models._enums import PostStatus, PostType
from app.schemas.post_metadata import (
    AnswerMetadata,
    JourneyEpisodeMetadata,
    JourneyEpMeta,
    PlanMetadata,
    QuestionMetadata,
    ReviewMetadata,
)
from app.tests.factories._base import BaseFactory
from app.tests.factories.region import RegionFactory
from app.tests.factories.user import UserFactory


def _default_metadata(post_type: PostType) -> dict:
    """Return a Pydantic-valid minimal dict for the given post type.

    Excluded keys (`type_tag` / aliased `__post_type__`) are not stored on
    Post.metadata — type is the canonical discriminator.
    """
    if post_type == PostType.REVIEW:
        d = ReviewMetadata(
            house_type="단독", size_pyeong=30, satisfaction_overall=4
        ).model_dump(by_alias=False, exclude_none=True)
    elif post_type == PostType.JOURNEY_EPISODE:
        d = JourneyEpisodeMetadata(
            journey_ep_meta=JourneyEpMeta(phase="입주", period_label="2026-04")
        ).model_dump(by_alias=False, exclude_none=True)
    elif post_type == PostType.QUESTION:
        d = QuestionMetadata().model_dump(by_alias=False)
    elif post_type == PostType.ANSWER:
        d = AnswerMetadata().model_dump(by_alias=False)
    elif post_type == PostType.PLAN:
        d = PlanMetadata(
            target_move_year=2027,
            budget_total_manwon_band="5000-10000",
            construction_intent="undecided",
        ).model_dump(by_alias=False)
    else:
        raise ValueError(f"Unknown post_type: {post_type}")
    d.pop("type_tag", None)
    return d


class PostFactory(BaseFactory):
    class Meta:
        model = Post
        exclude = ("author", "region")

    author = factory.SubFactory(UserFactory)
    author_id = factory.SelfAttribute("author.id")
    region = factory.SubFactory(RegionFactory)
    region_id = factory.SelfAttribute("region.id")

    type = PostType.REVIEW
    title = factory.Faker("sentence", nb_words=4, locale="ko_KR")
    body = factory.Faker("paragraph", nb_sentences=3, locale="ko_KR")
    status = PostStatus.DRAFT

    @factory.lazy_attribute
    def metadata_(self):
        return _default_metadata(self.type)


class ReviewPostFactory(PostFactory):
    type = PostType.REVIEW


class JourneyEpisodePostFactory(PostFactory):
    class Meta:
        model = Post
        exclude = ("author", "region", "journey")

    type = PostType.JOURNEY_EPISODE
    journey = factory.SubFactory("app.tests.factories.journey.JourneyFactory")
    journey_id = factory.SelfAttribute("journey.id")
    episode_no = factory.Sequence(lambda n: n + 1)


class QuestionPostFactory(PostFactory):
    type = PostType.QUESTION


class AnswerPostFactory(PostFactory):
    class Meta:
        model = Post
        exclude = ("author", "region", "parent_post")

    type = PostType.ANSWER
    parent_post = factory.SubFactory(QuestionPostFactory)
    parent_post_id = factory.SelfAttribute("parent_post.id")


class PlanPostFactory(PostFactory):
    type = PostType.PLAN
