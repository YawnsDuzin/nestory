from app.models.badge_application import BadgeApplication, BadgeEvidence
from app.models.comment import Comment
from app.models.image import Image
from app.models.interaction import (  # noqa: F401  # Table 객체 — metadata 등록용 (각 객체는 직접 import해 사용)
    journey_follows,
    post_likes,
    post_scraps,
    user_follows,
)
from app.models.interest_region import UserInterestRegion
from app.models.journey import Journey
from app.models.moderation import Announcement, AuditLog, Report
from app.models.notification import Notification
from app.models.post import Post
from app.models.post_validation import PostValidation
from app.models.region import Region
from app.models.tag import Tag  # post_tags Table 객체는 tag 모듈 로드 시 함께 등록
from app.models.user import BadgeLevel, User, UserRole

__all__ = [
    "Announcement",
    "AuditLog",
    "BadgeApplication",
    "BadgeEvidence",
    "BadgeLevel",
    "Comment",
    "Image",
    "Journey",
    "Notification",
    "Post",
    "PostValidation",
    "Region",
    "Report",
    "Tag",
    "User",
    "UserInterestRegion",
    "UserRole",
]
