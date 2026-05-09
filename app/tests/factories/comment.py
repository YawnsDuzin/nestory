"""Comment factory."""
import factory

from app.models import Comment
from app.models._enums import CommentStatus
from app.tests.factories._base import BaseFactory
from app.tests.factories.post import PostFactory
from app.tests.factories.user import UserFactory


class CommentFactory(BaseFactory):
    class Meta:
        model = Comment
        exclude = ("post", "author", "parent")

    post = factory.SubFactory(PostFactory)
    post_id = factory.SelfAttribute("post.id")
    author = factory.SubFactory(UserFactory)
    author_id = factory.SelfAttribute("author.id")
    parent = None
    parent_id = factory.LazyAttribute(lambda o: o.parent.id if o.parent else None)

    body = factory.Faker("paragraph", nb_sentences=2, locale="ko_KR")
    status = CommentStatus.VISIBLE
