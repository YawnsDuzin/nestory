"""Background worker process — PG-based job queue.

- Imports all handler modules so they self-register.
- Picks one queued job at a time (FOR UPDATE SKIP LOCKED).
- When the queue is empty, blocks on LISTEN nestory_jobs with a polling timeout.
- Handles SIGTERM/SIGINT for graceful shutdown.

Run: `python -m app.workers.runner`
"""
from __future__ import annotations

import os
import signal
import socket
import time
from threading import Event

import psycopg
import structlog

from app.config import get_settings
from app.db.session import SessionLocal
from app.workers import queue
from app.workers.handlers import dispatch, import_handlers

log = structlog.get_logger(__name__)
WORKER_ID = f"{socket.gethostname()}-{os.getpid()}"
NOTIFY_CHANNEL = queue.NOTIFY_CHANNEL
POLL_INTERVAL_SECONDS = 1.0
SHUTDOWN = Event()


def _install_signal_handlers() -> None:
    def _handler(signum: int, _frame) -> None:  # noqa: ANN001
        log.info("worker.shutdown_requested", signal=signum)
        SHUTDOWN.set()

    signal.signal(signal.SIGTERM, _handler)
    signal.signal(signal.SIGINT, _handler)


def process_one() -> bool:
    """Pick and run one job. Returns True if a job was processed, False if queue empty."""
    with SessionLocal() as db:
        job = queue.dequeue(db, worker_id=WORKER_ID)
        if job is None:
            return False

        kind = job.kind
        payload = dict(job.payload)
        try:
            dispatch(kind, payload)
        except Exception as exc:
            log.exception("worker.job_failed", job_id=job.id, kind=kind.value)
            queue.mark_failed(db, job, repr(exc))
            db.commit()
            return True

        queue.mark_succeeded(db, job)
        db.commit()
        log.info("worker.job_succeeded", job_id=job.id, kind=kind.value)
        return True


def _wait_for_notify(timeout: float) -> bool:
    """Block on LISTEN until NOTIFY arrives or timeout. Returns True if notified."""
    settings = get_settings()
    # psycopg 3 requires standard PG URL; strip SQLAlchemy driver prefix if present.
    dsn = settings.database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    try:
        with psycopg.connect(dsn, autocommit=True) as conn:
            conn.execute(f"LISTEN {NOTIFY_CHANNEL}")
            for _ in conn.notifies(timeout=timeout):
                return True
    except Exception:
        log.exception("worker.listen_error")
    return False


def run_loop() -> None:
    import_handlers()
    _install_signal_handlers()
    log.info("worker.start", worker_id=WORKER_ID)

    while not SHUTDOWN.is_set():
        try:
            processed = process_one()
        except Exception:
            log.exception("worker.process_one_error")
            time.sleep(POLL_INTERVAL_SECONDS)
            continue

        if processed:
            continue
        # Queue empty — wait for NOTIFY or timeout, then loop.
        _wait_for_notify(POLL_INTERVAL_SECONDS)

    log.info("worker.stop", worker_id=WORKER_ID)


if __name__ == "__main__":  # pragma: no cover
    run_loop()
