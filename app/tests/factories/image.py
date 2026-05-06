import factory
from factory.alchemy import SQLAlchemyModelFactory

from app.models import Image
from app.models._enums import ImageStatus
from app.tests.factories._session import _session_factory
from app.tests.factories.user import UserFactory


class ImageFactory(SQLAlchemyModelFactory):
    class Meta:
        model = Image
        sqlalchemy_session_factory = _session_factory
        sqlalchemy_session_persistence = "flush"

    file_path_orig = factory.Sequence(lambda n: f"/media/orig/2026/05/img{n}.jpg")
    status = ImageStatus.PROCESSING

    @factory.lazy_attribute
    def owner_id(self):
        return UserFactory().id
