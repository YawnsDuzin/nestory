"""PostValidation factory (Pillar V cross-validation votes)."""
import factory

from app.models import PostValidation
from app.models._enums import ValidationVote
from app.tests.factories._base import BaseFactory
from app.tests.factories.post import PostFactory
from app.tests.factories.user import RegionVerifiedUserFactory


class PostValidationFactory(BaseFactory):
    class Meta:
        model = PostValidation
        exclude = ("post", "validator")

    post = factory.SubFactory(PostFactory)
    post_id = factory.SelfAttribute("post.id")
    validator = factory.SubFactory(RegionVerifiedUserFactory)
    validator_user_id = factory.SelfAttribute("validator.id")

    vote = ValidationVote.CONFIRM
