"""Sanity tests for every factory. Each factory should produce a persisted row
and (where applicable) a Pydantic-valid metadata payload."""
from sqlalchemy.orm import Session

from app.models import BadgeLevel, Region, UserRole


def test_user_factory_creates_user(db: Session) -> None:
    from app.tests.factories import UserFactory

    user = UserFactory()
    assert user.id is not None
    assert user.email.endswith("@example.com")
    assert user.role == UserRole.USER
    assert user.badge_level == BadgeLevel.INTERESTED
    # password_hash must be a real argon2 hash, not plaintext
    assert user.password_hash and user.password_hash.startswith("$argon2")


def test_admin_user_factory(db: Session) -> None:
    from app.tests.factories import AdminUserFactory

    admin = AdminUserFactory()
    assert admin.role == UserRole.ADMIN


def test_region_factory_creates_region(db: Session) -> None:
    from app.tests.factories import RegionFactory

    r = RegionFactory()
    assert r.id is not None
    assert r.sido == "경기"
    assert r.slug.startswith("test-")


def test_region_factory_get_or_create(db: Session) -> None:
    from app.tests.factories import RegionFactory

    r1 = RegionFactory(slug="dup-slug")
    r2 = RegionFactory(slug="dup-slug")
    assert r1.id == r2.id


def test_region_verified_user_factory_has_primary_region(db: Session) -> None:
    from app.tests.factories import RegionVerifiedUserFactory

    u = RegionVerifiedUserFactory()
    assert u.badge_level == BadgeLevel.REGION_VERIFIED
    assert u.primary_region_id is not None
    region = db.query(Region).filter_by(id=u.primary_region_id).one()
    assert region is not None


def test_resident_user_factory(db: Session) -> None:
    from app.tests.factories import ResidentUserFactory

    u = ResidentUserFactory()
    assert u.badge_level == BadgeLevel.RESIDENT
    assert u.resident_verified_at is not None
    assert u.primary_region_id is not None  # inherited from RegionVerifiedUserFactory


def test_review_post_factory_metadata_validates(db: Session) -> None:
    from pydantic import TypeAdapter

    from app.models._enums import PostType
    from app.schemas.post_metadata import PostMetadata
    from app.tests.factories import ReviewPostFactory

    p = ReviewPostFactory()
    assert p.id is not None
    assert p.type == PostType.REVIEW
    payload = {**p.metadata_, "__post_type__": "review"}
    TypeAdapter(PostMetadata).validate_python(payload)


def test_journey_episode_post_factory_metadata_validates(db: Session) -> None:
    from pydantic import TypeAdapter

    from app.models._enums import PostType
    from app.schemas.post_metadata import PostMetadata
    from app.tests.factories import JourneyEpisodePostFactory

    p = JourneyEpisodePostFactory()
    assert p.type == PostType.JOURNEY_EPISODE
    assert p.journey_id is not None
    assert p.episode_no is not None
    payload = {**p.metadata_, "__post_type__": "journey_episode"}
    TypeAdapter(PostMetadata).validate_python(payload)


def test_question_post_factory_metadata_validates(db: Session) -> None:
    from pydantic import TypeAdapter

    from app.models._enums import PostType
    from app.schemas.post_metadata import PostMetadata
    from app.tests.factories import QuestionPostFactory

    p = QuestionPostFactory()
    assert p.type == PostType.QUESTION
    payload = {**p.metadata_, "__post_type__": "question"}
    TypeAdapter(PostMetadata).validate_python(payload)


def test_answer_post_factory_metadata_validates(db: Session) -> None:
    from pydantic import TypeAdapter

    from app.models._enums import PostType
    from app.schemas.post_metadata import PostMetadata
    from app.tests.factories import AnswerPostFactory

    p = AnswerPostFactory()
    assert p.type == PostType.ANSWER
    assert p.parent_post_id is not None
    payload = {**p.metadata_, "__post_type__": "answer"}
    TypeAdapter(PostMetadata).validate_python(payload)


def test_plan_post_factory_metadata_validates(db: Session) -> None:
    from pydantic import TypeAdapter

    from app.models._enums import PostType
    from app.schemas.post_metadata import PostMetadata
    from app.tests.factories import PlanPostFactory

    p = PlanPostFactory()
    assert p.type == PostType.PLAN
    payload = {**p.metadata_, "__post_type__": "plan"}
    TypeAdapter(PostMetadata).validate_python(payload)


def test_post_factory_override_metadata_field(db: Session) -> None:
    from app.tests.factories import ReviewPostFactory

    p = ReviewPostFactory(
        metadata_={"house_type": "단독", "size_pyeong": 30, "satisfaction_overall": 1}
    )
    assert p.metadata_["satisfaction_overall"] == 1


def test_comment_factory(db: Session) -> None:
    from app.models._enums import CommentStatus
    from app.tests.factories import CommentFactory

    c = CommentFactory()
    assert c.id is not None
    assert c.post_id is not None
    assert c.author_id is not None
    assert c.status == CommentStatus.VISIBLE


def test_journey_factory(db: Session) -> None:
    from app.models._enums import JourneyStatus
    from app.tests.factories import JourneyFactory

    j = JourneyFactory()
    assert j.id is not None
    assert j.author_id is not None
    assert j.region_id is not None
    assert j.status == JourneyStatus.IN_PROGRESS


def test_image_factory(db: Session) -> None:
    from app.models._enums import ImageStatus
    from app.tests.factories import ImageFactory

    img = ImageFactory()
    assert img.id is not None
    assert img.owner_id is not None
    assert img.file_path_orig.startswith("images/")
    assert img.status == ImageStatus.READY


def test_badge_application_factory(db: Session) -> None:
    from app.models._enums import BadgeApplicationStatus, BadgeRequestedLevel
    from app.tests.factories import BadgeApplicationFactory

    app = BadgeApplicationFactory()
    assert app.id is not None
    assert app.user_id is not None
    assert app.region_id is not None
    assert app.requested_level == BadgeRequestedLevel.REGION_VERIFIED
    assert app.status == BadgeApplicationStatus.PENDING


def test_badge_evidence_factory(db: Session) -> None:
    from app.models._enums import EvidenceType
    from app.tests.factories import BadgeEvidenceFactory

    e = BadgeEvidenceFactory()
    assert e.id is not None
    assert e.application_id is not None
    assert e.evidence_type == EvidenceType.UTILITY_BILL
    assert e.file_path.startswith("evidence/")


def test_notification_factory(db: Session) -> None:
    from app.models._enums import NotificationType
    from app.tests.factories import NotificationFactory

    n = NotificationFactory()
    assert n.id is not None
    assert n.user_id is not None
    assert n.type == NotificationType.SYSTEM
    assert n.is_read is False


def test_user_interest_region_factory(db: Session) -> None:
    from app.tests.factories import UserInterestRegionFactory

    uir = UserInterestRegionFactory()
    assert uir.user_id is not None
    assert uir.region_id is not None
    assert uir.priority == 1


def test_job_factory(db: Session) -> None:
    from app.models._enums import JobKind, JobStatus
    from app.tests.factories import JobFactory

    j = JobFactory()
    assert j.id is not None
    assert j.kind == JobKind.NOTIFICATION
    assert j.status == JobStatus.QUEUED
    assert j.payload == {}


def test_tag_factory(db: Session) -> None:
    from app.tests.factories import TagFactory

    t = TagFactory()
    assert t.id is not None
    assert t.slug.startswith("tag-")


def test_tag_factory_get_or_create(db: Session) -> None:
    from app.tests.factories import TagFactory

    t1 = TagFactory(slug="dup-tag")
    t2 = TagFactory(slug="dup-tag")
    assert t1.id == t2.id


def test_announcement_factory(db: Session) -> None:
    from app.tests.factories import AnnouncementFactory

    a = AnnouncementFactory()
    assert a.id is not None
    assert a.author_id is not None
    assert a.pinned is False


def test_audit_log_factory(db: Session) -> None:
    from app.models._enums import AuditAction
    from app.tests.factories import AuditLogFactory

    log = AuditLogFactory()
    assert log.id is not None
    assert log.actor_id is not None
    assert log.action == AuditAction.BADGE_APPROVED
    assert log.target_type == "badge_applications"


def test_report_factory(db: Session) -> None:
    from app.models._enums import ReportReason, ReportStatus
    from app.tests.factories import ReportFactory

    r = ReportFactory()
    assert r.id is not None
    assert r.reporter_id is not None
    assert r.target_type == "posts"
    assert r.reason == ReportReason.SPAM
    assert r.status == ReportStatus.PENDING


def test_post_validation_factory(db: Session) -> None:
    from app.models._enums import ValidationVote
    from app.tests.factories import PostValidationFactory

    pv = PostValidationFactory()
    assert pv.id is not None
    assert pv.post_id is not None
    assert pv.validator_user_id is not None
    assert pv.vote == ValidationVote.CONFIRM
