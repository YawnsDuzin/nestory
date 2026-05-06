"""evidence_cleanup handler — delete evidence files + DB rows for a given application_id.

Triggered:
- 30 days after approve (PRD §8.1: 승인 30일 후 자동 삭제)
- Immediately after reject

Payload: {"application_id": int}
"""
from typing import Any

import structlog

from app.db.session import SessionLocal
from app.models import BadgeEvidence
from app.models._enums import JobKind
from app.services import evidence_storage
from app.workers.handlers import register

log = structlog.get_logger(__name__)


@register(JobKind.EVIDENCE_CLEANUP)
def handle_evidence_cleanup(payload: dict[str, Any]) -> None:
    application_id = payload.get("application_id")
    if not isinstance(application_id, int):
        raise ValueError(f"application_id required in payload, got {payload!r}")

    with SessionLocal() as db:
        evidences = (
            db.query(BadgeEvidence).filter_by(application_id=application_id).all()
        )
        rows_deleted = 0
        for e in evidences:
            db.delete(e)
            rows_deleted += 1
        files_deleted = evidence_storage.delete_all_for_application(application_id)
        db.commit()

    log.info(
        "handler.evidence_cleanup.done",
        application_id=application_id,
        rows_deleted=rows_deleted,
        files_deleted=files_deleted,
    )
