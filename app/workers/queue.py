"""PostgreSQL-based job queue primitives.

Reference: PRD §6.7 v1.1 [A1].

- enqueue() inserts a row and emits NOTIFY on the `nestory_jobs` channel.
- dequeue() picks one queued job atomically using FOR UPDATE SKIP LOCKED.
- mark_succeeded()/mark_failed() finalize a running job; mark_failed implements
  exponential backoff and DEAD transition after max_attempts.
"""
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import Job
from app.models._enums import JobKind, JobStatus

NOTIFY_CHANNEL = "nestory_jobs"


def enqueue(
    db: Session,
    kind: JobKind,
    payload: dict[str, Any],
    *,
    run_after: datetime | None = None,
    max_attempts: int = 5,
) -> Job:
    """Insert a queued job and emit NOTIFY. Caller must commit."""
    job = Job(
        kind=kind,
        payload=payload,
        run_after=run_after or datetime.now(UTC),
        max_attempts=max_attempts,
    )
    db.add(job)
    db.flush()
    # NOTIFY does not support bind parameters; kind.value is an enum-controlled
    # literal so embedding it directly is safe (no SQL injection risk).
    db.execute(text(f"NOTIFY {NOTIFY_CHANNEL}, '{kind.value}'"))
    return job


def dequeue(db: Session, *, worker_id: str) -> Job | None:
    """Pick one queued job whose run_after has elapsed.

    Uses FOR UPDATE SKIP LOCKED for safe concurrent worker pickup.
    Returns None if queue is empty. Caller must commit on success/failure.
    """
    stmt = (
        select(Job)
        .where(
            Job.status == JobStatus.QUEUED,
            Job.run_after <= datetime.now(UTC),
        )
        .order_by(Job.run_after.asc(), Job.id.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    job = db.scalar(stmt)
    if job is None:
        return None
    job.status = JobStatus.RUNNING
    job.locked_at = datetime.now(UTC)
    job.locked_by = worker_id
    job.attempts += 1
    db.flush()
    return job


def mark_succeeded(db: Session, job: Job) -> None:
    job.status = JobStatus.SUCCEEDED
    job.completed_at = datetime.now(UTC)
    job.locked_at = None
    job.locked_by = None
    db.flush()


def mark_failed(db: Session, job: Job, error: str) -> None:
    """Failed job: re-queue with exponential backoff or mark DEAD if maxed out."""
    job.last_error = error[:5000]
    if job.attempts >= job.max_attempts:
        job.status = JobStatus.DEAD
        job.completed_at = datetime.now(UTC)
        job.locked_at = None
        job.locked_by = None
    else:
        backoff_seconds = 60 * (2 ** (job.attempts - 1))
        job.status = JobStatus.QUEUED
        job.run_after = datetime.now(UTC) + timedelta(seconds=backoff_seconds)
        job.locked_at = None
        job.locked_by = None
    db.flush()
