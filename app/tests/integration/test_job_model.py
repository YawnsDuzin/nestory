from sqlalchemy.orm import Session

from app.models import Job
from app.models._enums import JobKind, JobStatus


def test_create_queued_job(db: Session) -> None:
    j = Job(
        kind=JobKind.IMAGE_RESIZE,
        payload={"image_id": 42, "source_path": "/media/orig/x.jpg"},
    )
    db.add(j)
    db.flush()
    assert j.status == JobStatus.QUEUED
    assert j.attempts == 0
    assert j.max_attempts == 5
    assert j.run_after is not None
    assert j.locked_at is None


def test_job_jsonb_payload_round_trip(db: Session) -> None:
    j = Job(
        kind=JobKind.NOTIFICATION,
        payload={"user_id": 1, "type": "badge_approved", "channel": "alimtalk"},
    )
    db.add(j)
    db.flush()
    db.expire(j)
    fetched = db.get(Job, j.id)
    assert fetched.payload["channel"] == "alimtalk"
