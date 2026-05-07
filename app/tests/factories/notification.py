"""Notification factory."""
import factory

from app.models import Notification
from app.models._enums import NotificationType
from app.tests.factories._base import BaseFactory
from app.tests.factories.user import UserFactory


class NotificationFactory(BaseFactory):
    class Meta:
        model = Notification
        exclude = ("user",)

    user = factory.SubFactory(UserFactory)
    user_id = factory.SelfAttribute("user.id")

    type = NotificationType.SYSTEM
    is_read = False
