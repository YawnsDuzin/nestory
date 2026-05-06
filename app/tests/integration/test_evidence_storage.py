import io
from pathlib import Path

import pytest

from app.config import get_settings
from app.services import evidence_storage


@pytest.fixture(autouse=True)
def _isolate_evidence_dir(tmp_path, monkeypatch):
    """Each test gets a fresh tmp evidence dir — settings cache cleared."""
    monkeypatch.setenv("EVIDENCE_BASE_PATH", str(tmp_path / "evidence"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_store_creates_file_with_uuid_name() -> None:
    path = evidence_storage.store(
        application_id=42,
        filename="utility_bill.jpg",
        stream=io.BytesIO(b"fake-jpg-content"),
        now_year=2026,
        now_month=5,
    )
    p = Path(path)
    assert p.exists()
    assert p.suffix == ".jpg"
    assert "/2026/05/42/" in path.replace("\\", "/")
    assert p.read_bytes() == b"fake-jpg-content"


def test_store_rejects_disallowed_extension() -> None:
    with pytest.raises(ValueError, match="not allowed"):
        evidence_storage.store(
            application_id=1,
            filename="evil.exe",
            stream=io.BytesIO(b"x"),
            now_year=2026,
            now_month=5,
        )


def test_store_rejects_oversize_file() -> None:
    big = io.BytesIO(b"x" * (evidence_storage.MAX_BYTES + 1))
    with pytest.raises(ValueError, match="too large"):
        evidence_storage.store(
            application_id=1, filename="big.jpg", stream=big, now_year=2026, now_month=5
        )


def test_delete_removes_file() -> None:
    path = evidence_storage.store(
        application_id=1,
        filename="x.jpg",
        stream=io.BytesIO(b"x"),
        now_year=2026,
        now_month=5,
    )
    assert evidence_storage.delete(path) is True
    assert evidence_storage.delete(path) is False  # 두 번째는 missing


def test_delete_all_for_application() -> None:
    p1 = evidence_storage.store(
        application_id=99, filename="a.jpg", stream=io.BytesIO(b"a"), now_year=2026, now_month=5
    )
    p2 = evidence_storage.store(
        application_id=99, filename="b.pdf", stream=io.BytesIO(b"b"), now_year=2026, now_month=5
    )
    n = evidence_storage.delete_all_for_application(99)
    assert n == 2
    assert not Path(p1).exists()
    assert not Path(p2).exists()
