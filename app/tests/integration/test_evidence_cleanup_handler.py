import io
from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import BadgeApplication, BadgeEvidence, Region, User
from app.models._enums import (
    BadgeRequestedLevel,
    EvidenceType,
)
from app.services import evidence_storage
from app.workers.handlers import dispatch, import_handlers
from app.workers.handlers.evidence_cleanup import handle_evidence_cleanup


@pytest.fixture(autouse=True)
def _isolate_evidence_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("EVIDENCE_BASE_PATH", str(tmp_path / "evidence"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _make_application_with_files(db: Session) -> int:
    ts = int(datetime.now(UTC).timestamp() * 1_000_000)
    user = User(email=f"t{ts}@x.com", username=f"u{ts}", display_name="t", password_hash="x")
    region = Region(sido="경기", sigungu="양평군", slug=f"yp-{ts}")
    db.add_all([user, region])
    db.flush()
    app_obj = BadgeApplication(
        user_id=user.id,
        requested_level=BadgeRequestedLevel.RESIDENT,
        region_id=region.id,
    )
    db.add(app_obj)
    db.flush()

    # Real files
    p1 = evidence_storage.store(
        application_id=app_obj.id,
        filename="bill.jpg",
        stream=io.BytesIO(b"a"),
        now_year=2026,
        now_month=5,
    )
    p2 = evidence_storage.store(
        application_id=app_obj.id,
        filename="contract.pdf",
        stream=io.BytesIO(b"b"),
        now_year=2026,
        now_month=5,
    )
    db.add_all([
        BadgeEvidence(
            application_id=app_obj.id,
            evidence_type=EvidenceType.UTILITY_BILL,
            file_path=p1,
        ),
        BadgeEvidence(
            application_id=app_obj.id,
            evidence_type=EvidenceType.CONTRACT,
            file_path=p2,
        ),
    ])
    db.commit()
    return app_obj.id


def test_handler_deletes_files_and_rows(db: Session) -> None:
    app_id = _make_application_with_files(db)
    handle_evidence_cleanup({"application_id": app_id})
    db.expire_all()
    remaining = db.query(BadgeEvidence).filter_by(application_id=app_id).all()
    assert remaining == []


def test_handler_idempotent(db: Session) -> None:
    app_id = _make_application_with_files(db)
    handle_evidence_cleanup({"application_id": app_id})
    # Second call should not raise — files+rows already gone
    handle_evidence_cleanup({"application_id": app_id})


def test_handler_invalid_payload() -> None:
    with pytest.raises(ValueError, match="application_id required"):
        handle_evidence_cleanup({})


def test_dispatch_via_registry(db: Session) -> None:
    import_handlers()
    app_id = _make_application_with_files(db)
    from app.models._enums import JobKind
    dispatch(JobKind.EVIDENCE_CLEANUP, {"application_id": app_id})
    db.expire_all()
    assert db.query(BadgeEvidence).filter_by(application_id=app_id).count() == 0
