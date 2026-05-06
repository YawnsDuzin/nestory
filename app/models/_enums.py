import enum


class PostType(str, enum.Enum):
    REVIEW = "review"
    JOURNEY_EPISODE = "journey_episode"
    QUESTION = "question"
    ANSWER = "answer"
    PLAN = "plan"


class PostStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    HIDDEN = "hidden"


class JourneyStatus(str, enum.Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class CommentStatus(str, enum.Enum):
    VISIBLE = "visible"
    HIDDEN = "hidden"


class ImageStatus(str, enum.Enum):
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class BadgeApplicationStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class BadgeRequestedLevel(str, enum.Enum):
    REGION_VERIFIED = "region_verified"
    RESIDENT = "resident"


class EvidenceType(str, enum.Enum):
    UTILITY_BILL = "utility_bill"
    CONTRACT = "contract"
    BUILDING_CERT = "building_cert"
    GEO_SELFIE = "geo_selfie"


class ValidationVote(str, enum.Enum):
    CONFIRM = "confirm"
    DISPUTE = "dispute"


class NotificationType(str, enum.Enum):
    BADGE_APPROVED = "badge_approved"
    BADGE_REJECTED = "badge_rejected"
    POST_COMMENT = "post_comment"
    POST_LIKED = "post_liked"
    JOURNEY_NEW_EPISODE = "journey_new_episode"
    QUESTION_ANSWERED = "question_answered"
    REVALIDATION_PROMPT = "revalidation_prompt"
    TIMELAPSE_REMIND = "timelapse_remind"
    SYSTEM = "system"


class ReportReason(str, enum.Enum):
    SPAM = "spam"
    AD = "ad"
    OFFENSIVE = "offensive"
    PRIVACY = "privacy"
    PEER_DISPUTE = "peer_dispute"
    OTHER = "other"


class ReportStatus(str, enum.Enum):
    PENDING = "pending"
    RESOLVED = "resolved"
    REJECTED = "rejected"


class AuditAction(str, enum.Enum):
    BADGE_APPROVED = "badge_approved"
    BADGE_REJECTED = "badge_rejected"
    CONTENT_HIDDEN = "content_hidden"
    USER_BANNED = "user_banned"
    REPORT_RESOLVED = "report_resolved"
    ANNOUNCEMENT_PUBLISHED = "announcement_published"


class JobKind(str, enum.Enum):
    IMAGE_RESIZE = "image_resize"
    NOTIFICATION = "notification"
    REVALIDATION_CHECK = "revalidation_check"
    TIMELAPSE_REMIND = "timelapse_remind"
    EVIDENCE_CLEANUP = "evidence_cleanup"


class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DEAD = "dead"
