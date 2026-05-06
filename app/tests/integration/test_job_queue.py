from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models._enums import JobKind, JobStatus
from app.workers import queue


def test_enqueue_creates_queued_job(db: Session) -> None:
    j = queue.enqueue(db, JobKind.IMAGE_RESIZE, {"image_id": 1})
    db.commit()
    assert j.status == JobStatus.QUEUED
    assert j.payload == {"image_id": 1}


def test_dequeue_picks_oldest_due_job(db: Session) -> None:
    queue.enqueue(db, JobKind.IMAGE_RESIZE, {"image_id": 1})
    queue.enqueue(db, JobKind.NOTIFICATION, {"user_id": 1})
    db.commit()

    j = queue.dequeue(db, worker_id="test-worker")
    db.commit()
    assert j is not None
    assert j.status == JobStatus.RUNNING
    assert j.locked_by == "test-worker"
    assert j.attempts == 1


def test_dequeue_skips_future_run_after(db: Session) -> None:
    future = datetime.now(UTC) + timedelta(hours=1)
    queue.enqueue(db, JobKind.IMAGE_RESIZE, {"x": 1}, run_after=future)
    db.commit()
    assert queue.dequeue(db, worker_id="w1") is None


def test_dequeue_returns_none_for_empty_queue(db: Session) -> None:
    assert queue.dequeue(db, worker_id="w1") is None


def test_mark_succeeded(db: Session) -> None:
    queue.enqueue(db, JobKind.IMAGE_RESIZE, {})
    db.commit()
    j = queue.dequeue(db, worker_id="w1")
    queue.mark_succeeded(db, j)
    db.commit()
    assert j.status == JobStatus.SUCCEEDED
    assert j.completed_at is not None
    assert j.locked_by is None


def test_mark_failed_retry_with_backoff(db: Session) -> None:
    queue.enqueue(db, JobKind.IMAGE_RESIZE, {}, max_attempts=3)
    db.commit()
    j = queue.dequeue(db, worker_id="w1")
    before = datetime.now(UTC)
    queue.mark_failed(db, j, "boom")
    db.commit()
    assert j.status == JobStatus.QUEUED
    assert j.run_after > before  # backoff applied
    assert j.last_error == "boom"
    assert j.attempts == 1


def test_mark_failed_dead_after_max_attempts(db: Session) -> None:
    queue.enqueue(db, JobKind.IMAGE_RESIZE, {}, max_attempts=2)
    db.commit()

    # 1st attempt
    j = queue.dequeue(db, worker_id="w1")
    queue.mark_failed(db, j, "err1")
    db.commit()
    # Move run_after to past so it can be dequeued again immediately
    j.run_after = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()

    # 2nd attempt
    j2 = queue.dequeue(db, worker_id="w1")
    assert j2.id == j.id
    queue.mark_failed(db, j2, "err2")
    db.commit()
    assert j2.status == JobStatus.DEAD
    assert j2.completed_at is not None
    assert j2.attempts == 2
