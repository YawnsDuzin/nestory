"""Private evidence file storage (filesystem).

Files are stored under EVIDENCE_BASE_PATH and never exposed via static mounts.
Path layout: {base}/{YYYY}/{MM}/{application_id}/{uuid}.{ext}

Reference: PRD §6.4 (저장 레이아웃) · §8.1 (비공개 디렉토리).
"""
from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import BinaryIO

from app.config import get_settings

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf", ".heic"}
MAX_BYTES = 10 * 1024 * 1024  # 10MB


def _base_dir() -> Path:
    return Path(get_settings().evidence_base_path).resolve()


def store(
    *,
    application_id: int,
    filename: str,
    stream: BinaryIO,
    now_year: int,
    now_month: int,
) -> str:
    """Persist a file to the private evidence dir. Returns the absolute path string.

    - Validates extension against ALLOWED_EXTENSIONS.
    - Validates size against MAX_BYTES (raises ValueError if exceeded).
    - Generates a uuid4 filename to avoid path traversal.
    """
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError(f"File extension '{suffix}' not allowed")

    target_dir = _base_dir() / f"{now_year:04d}" / f"{now_month:02d}" / str(application_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"{uuid.uuid4().hex}{suffix}"

    written = 0
    with target_path.open("wb") as out:
        while True:
            chunk = stream.read(64 * 1024)
            if not chunk:
                break
            written += len(chunk)
            if written > MAX_BYTES:
                out.close()
                target_path.unlink(missing_ok=True)
                raise ValueError(f"File too large (> {MAX_BYTES} bytes)")
            out.write(chunk)

    return str(target_path)


def delete(path: str) -> bool:
    """Delete a stored file. Returns True if deleted, False if missing."""
    p = Path(path)
    if not p.exists():
        return False
    p.unlink()
    # Try to clean up empty parent dirs (year/month/application) up to base.
    base = _base_dir()
    parent = p.parent
    while parent != base and parent.exists() and not any(parent.iterdir()):
        parent.rmdir()
        parent = parent.parent
    return True


def delete_all_for_application(application_id: int) -> int:
    """Delete the entire {base}/{YYYY}/{MM}/{application_id}/ directory tree.

    Returns count of files deleted. Used by evidence_cleanup worker.
    """
    base = _base_dir()
    deleted = 0
    if not base.exists():
        return 0
    for year_dir in base.iterdir():
        if not year_dir.is_dir():
            continue
        for month_dir in year_dir.iterdir():
            if not month_dir.is_dir():
                continue
            app_dir = month_dir / str(application_id)
            if app_dir.exists() and app_dir.is_dir():
                deleted += sum(1 for _ in app_dir.rglob("*") if _.is_file())
                shutil.rmtree(app_dir)
                # cleanup empty parents
                if not any(month_dir.iterdir()):
                    month_dir.rmdir()
                    if not any(year_dir.iterdir()):
                        year_dir.rmdir()
    return deleted
