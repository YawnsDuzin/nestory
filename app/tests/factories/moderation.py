"""Announcement, AuditLog, Report factories."""
import factory

from app.models import Announcement, AuditLog, Report
from app.models._enums import AuditAction, ReportReason, ReportStatus
from app.tests.factories._base import BaseFactory
from app.tests.factories.user import AdminUserFactory, UserFactory


class AnnouncementFactory(BaseFactory):
    class Meta:
        model = Announcement
        exclude = ("author",)

    author = factory.SubFactory(AdminUserFactory)
    author_id = factory.SelfAttribute("author.id")

    title = factory.Faker("sentence", nb_words=4, locale="ko_KR")
    body = factory.Faker("paragraph", nb_sentences=2, locale="ko_KR")
    pinned = False


class AuditLogFactory(BaseFactory):
    class Meta:
        model = AuditLog
        exclude = ("actor",)

    actor = factory.SubFactory(AdminUserFactory)
    actor_id = factory.SelfAttribute("actor.id")

    action = AuditAction.BADGE_APPROVED
    target_type = "badge_applications"
    target_id = factory.Sequence(lambda n: n + 1)


class ReportFactory(BaseFactory):
    class Meta:
        model = Report
        exclude = ("reporter",)

    reporter = factory.SubFactory(UserFactory)
    reporter_id = factory.SelfAttribute("reporter.id")

    target_type = "posts"
    target_id = factory.Sequence(lambda n: n + 1)
    reason = ReportReason.SPAM
    status = ReportStatus.PENDING
