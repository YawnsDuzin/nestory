"""image_resize handler — Phase 1.3에서 실제 Pillow 변환 구현. P1.1은 stub."""
from typing import Any

import structlog

from app.models._enums import JobKind
from app.workers.handlers import register

log = structlog.get_logger(__name__)


@register(JobKind.IMAGE_RESIZE)
def handle_image_resize(payload: dict[str, Any]) -> None:
    log.info("handler.image_resize.received", payload=payload)
