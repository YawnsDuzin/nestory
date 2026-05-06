"""End-to-end test: enqueue → dequeue → handler dispatch round-trip.

Calls process_one() directly rather than spawning the runner,
keeping the test deterministic and fast.
"""
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models import Job
from app.models._enums import JobKind, JobStatus
from app.workers import queue
from app.workers.handlers import import_handlers
from app.workers.runner import process_one


def test_enqueue_then_process_one_marks_succeeded(db: Session) -> None:
    import_handlers()
    queue.enqueue(db, JobKind.IMAGE_RESIZE, {"image_id": 1})
    db.commit()

    processed = process_one()
    assert processed is True

    # Re-fetch via fresh session to bypass identity map
    db.expire_all()
    job = db.query(Job).order_by(Job.id.desc()).first()
    assert job.status == JobStatus.SUCCEEDED
    assert job.completed_at is not None


def test_process_one_returns_false_for_empty_queue(db: Session) -> None:
    import_handlers()
    assert process_one() is False


def test_unknown_kind_marks_dead_eventually(db: Session) -> None:
    """Job with no registered handler — handler raises, job retries to DEAD."""
    import_handlers()
    j = queue.enqueue(db, JobKind.EVIDENCE_CLEANUP, {}, max_attempts=2)
    db.commit()

    # 1st attempt — fail (no handler), gets backoff
    process_one()
    db.expire_all()
    job = db.get(Job, j.id)
    assert job.status == JobStatus.QUEUED
    assert job.attempts == 1

    # Move run_after to past
    job.run_after = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()

    # 2nd attempt — fail again, transitions to DEAD
    process_one()
    db.expire_all()
    job = db.get(Job, j.id)
    assert job.status == JobStatus.DEAD
    assert job.attempts == 2
    assert job.last_error is not None


def test_alembic_head_creates_all_p11_tables(db: Session) -> None:
    """Sanity check — every P1.1 model is reachable as a SQL relation."""
    from sqlalchemy import inspect

    inspector = inspect(db.get_bind())
    tables = set(inspector.get_table_names())
    expected = {
        "users", "regions", "user_interest_regions",
        "images", "journeys", "posts", "post_validations",
        "comments", "tags", "post_tags",
        "post_likes", "post_scraps", "user_follows", "journey_follows",
        "badge_applications", "badge_evidence",
        "notifications", "reports", "audit_logs", "announcements",
        "jobs",
    }
    missing = expected - tables
    assert not missing, f"Missing tables: {missing}"
