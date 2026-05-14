"""PostHog event capture — wired to posthog SDK in production.

PRD §14.5 이벤트 카탈로그 + §8.2 PII 정책.
emit no-op 조건:
- app_env != "production" (개발/테스트 데이터 오염 방지)
- posthog_api_key 빈 값 (운영자 미설정)
"""
import hashlib
import logging
import uuid
from enum import Enum
from functools import lru_cache
from typing import Any

from app.config import get_settings

log = logging.getLogger(__name__)


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

    # P1.5b — home community pulse
    HOME_FEED_CARD_CLICK = "home_feed_card_click"
    HOME_FAB_OPEN = "home_fab_open"
    HOME_FAB_ACTION = "home_fab_action"
    HOME_REGION_ACTIVITY_CLICK = "home_region_activity_click"


@lru_cache(maxsize=1)
def _get_client():  # type: ignore[no-untyped-def]
    """PostHog 클라이언트 — process 단위 캐시. API key 빈 값이면 None 반환."""
    settings = get_settings()
    if not settings.posthog_api_key:
        return None
    import posthog
    posthog.api_key = settings.posthog_api_key
    posthog.host = settings.posthog_host
    return posthog


def _distinct_id(user_id: int | None, anon_id: str | None = None) -> str:
    """로그인 user_id → SHA-256 해시; 익명 → anon_id 그대로 (없으면 새 UUID)."""
    if user_id is not None:
        return hashlib.sha256(str(user_id).encode()).hexdigest()
    return anon_id or f"anon-{uuid.uuid4()}"


def emit(
    event: EventName,
    distinct_id_hash: str | None = None,
    props: dict[str, Any] | None = None,
) -> None:
    """Capture event to PostHog. PII는 props에 절대 포함 금지 (호출자 책임)."""
    settings = get_settings()
    if settings.app_env != "production":
        return None
    client = _get_client()
    if client is None:
        return None
    try:
        client.capture(
            distinct_id=distinct_id_hash or f"anon-{uuid.uuid4()}",
            event=event.value,
            properties=props or {},
        )
    except Exception as e:  # noqa: BLE001
        log.warning("posthog.capture.failed event=%s error=%s", event.value, e)


__all__ = ["EventName", "emit"]
