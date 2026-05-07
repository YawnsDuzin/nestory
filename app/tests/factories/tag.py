"""Tag factory with get-or-create on slug."""
import factory

from app.models import Tag
from app.tests.factories._base import BaseFactory


class TagFactory(BaseFactory):
    class Meta:
        model = Tag
        sqlalchemy_get_or_create = ("slug",)

    name = factory.Sequence(lambda n: f"태그{n}")
    slug = factory.Sequence(lambda n: f"tag-{n}")
