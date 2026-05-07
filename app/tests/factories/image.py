"""Image factory."""
import factory

from app.models import Image
from app.models._enums import ImageStatus
from app.tests.factories._base import BaseFactory
from app.tests.factories.user import UserFactory


class ImageFactory(BaseFactory):
    class Meta:
        model = Image
        exclude = ("owner",)

    owner = factory.SubFactory(UserFactory)
    owner_id = factory.SelfAttribute("owner.id")

    file_path_orig = factory.Sequence(lambda n: f"images/{n}/orig.jpg")
    status = ImageStatus.READY
    order_idx = 0
