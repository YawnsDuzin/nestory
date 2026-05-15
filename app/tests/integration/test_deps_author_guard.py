"""require_author dependency — smoke test.

본 파일은 import·factory 호출 가능성만 검증한다.
실제 권한 동작(404 missing/soft-deleted, 403 non-author, 200 owner)은
Task 7·8·9·10의 라우트 통합 테스트에서 검증한다.
"""
from __future__ import annotations

from app.deps import require_author


def test_require_author_is_callable_factory() -> None:
    """Factory가 callable이고, 호출 결과가 FastAPI dependency로 쓸 callable이어야 한다."""
    assert callable(require_author)
    dep = require_author("post_id")
    assert callable(dep)
