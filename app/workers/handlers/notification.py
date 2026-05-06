"""notification handler — P1.5에서 실제 카카오 알림톡·이메일 발송 구현. P1.1은 stub."""
from typing import Any

import structlog

from app.models._enums import JobKind
from app.workers.handlers import register

log = structlog.get_logger(__name__)


@register(JobKind.NOTIFICATION)
def handle_notification(payload: dict[str, Any]) -> None:
    log.info("handler.notification.received", payload=payload)
