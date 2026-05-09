"""PostHog event catalog (PRD §14.5).

이벤트 이름은 자유 문자열 금지 — `EventName` enum으로만 dispatch.
실제 PostHog client wiring은 P1.5에서 추가. 현재 `emit`은 no-op.
PII는 어떤 이벤트 props에도 포함하지 말 것 (PRD §8.2).
"""
from enum import Enum
from typing import Any


class EventName(str, Enum):
    # P0 / P1.2 — auth & badge
    USER_SIGNED_UP = "user_signed_up"
    USER_LOGGED_IN = "user_logged_in"
    BADGE_APPLIED = "badge_applied"
    BADGE_APPROVED = "badge_approved"

    # P1.3 — content & images
    POST_PUBLISHED = "post_published"
    IMAGE_UPLOADED = "image_uploaded"

    # P1.4 — discovery & interactions
    HUB_VIEWED = "hub_viewed"
    DISCOVER_VIEWED = "discover_viewed"
    SEARCH_QUERY = "search_query"
    POST_VIEWED = "post_viewed"
    POST_LIKED = "post_liked"
    POST_SCRAPPED = "post_scrapped"
    COMMENT_POSTED = "comment_posted"
    PROFILE_VIEWED = "profile_viewed"

    # P1.5 / P1.4b — Region Match Wizard
    MATCH_WIZARD_STARTED = "match_wizard_started"
    MATCH_WIZARD_SUBMITTED = "match_wizard_submitted"
    MATCH_RESULT_VIEWED = "match_result_viewed"

    # P1.5a — notifications
    NOTIFICATION_OPENED = "notification_opened"


def emit(
    event: EventName,
    distinct_id_hash: str | None = None,
    props: dict[str, Any] | None = None,
) -> None:
    """No-op until P1.5 PostHog wiring.

    `distinct_id_hash` is the SHA-256 of (user_id || ip salt) — never raw user_id.
    `props` must contain no PII (no email, no phone, no full address).
    """
    return None


__all__ = ["EventName", "emit"]
