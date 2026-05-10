"""CLAUDE.md '안티패턴' 자동 검증.

세 가지 코드 리뷰 차단 사유를 기계적으로 검증한다:

1. routes에서 ORM 직접 쿼리 (`db.query(...)`) — services 레이어로 이전해야 함
2. services 내부에서 `request.session` 접근 — 라우트가 User를 인자로 전달해야 함
3. tests에서 직접 `Model(...)` 생성자 호출 — factory 사용 필수
   (단, IntegrityError 검증·default 검증·생성 SUT 3 경우는 ALLOWLIST)

사용:
    uv run python scripts/check_anti_patterns.py

CI / pre-commit hook에서 실행. exit 0 = clean, exit 1 = 위반 존재.

신규 위반 발견 시:
- (1)·(2): 코드를 services 레이어로 이전
- (3): factory 사용으로 변경하거나, 정당한 사유면 ALLOWLIST에 파일명 추가 + 주석으로 사유 기록
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ROUTERS_DIR = ROOT / "app" / "routers"
SERVICES_DIR = ROOT / "app" / "services"
TESTS_DIR = ROOT / "app" / "tests" / "integration"

# 알려진 위반 — P1.6 cleanup 대상. 새로 추가하지 말 것.
ROUTER_DBQ_ALLOWLIST: set[str] = {
    "content.py",  # 14건 — P1.6에서 services로 이전 예정
    "journey.py",
    "me.py",
}

# 정당한 직접 생성자 사용 (CLAUDE.md "테스트 데이터 (factory-boy)" 3 경우)
TEST_CTOR_ALLOWLIST: set[str] = {
    "test_image_model.py",  # 모델 default 검증
    "test_tag_model.py",  # IntegrityError 검증
    "test_interest_region_model.py",  # IntegrityError 검증
    "test_auth_service_db.py",  # 생성 service SUT
    "test_job_queue.py",  # 생성 queue SUT
    "test_notification_service.py",  # notification 생성 service SUT
    "test_notification_emit_integration.py",  # 의도적 spec drift (handoff 참조)
}

CTOR_PATTERN = re.compile(
    r"^\s*(?:\w+\s*=\s*)?"
    r"(Post|Journey|Region|Comment|Image|Tag|Notification|BadgeApplication|Job)\("
)


def _check_router_db_query() -> list[str]:
    violations: list[str] = []
    for py in sorted(ROUTERS_DIR.glob("*.py")):
        if py.name in ROUTER_DBQ_ALLOWLIST or py.name.startswith("__"):
            continue
        for i, line in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
            if "db.query(" in line:
                rel = py.relative_to(ROOT).as_posix()
                violations.append(f"{rel}:{i}: db.query in router — move to service layer")
    return violations


def _check_service_request_session() -> list[str]:
    violations: list[str] = []
    for py in sorted(SERVICES_DIR.glob("*.py")):
        if py.name.startswith("__"):
            continue
        for i, line in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
            if "request.session" in line or "request.cookies" in line:
                rel = py.relative_to(ROOT).as_posix()
                violations.append(
                    f"{rel}:{i}: request.session/cookies in service — pass User as arg from route"
                )
    return violations


def _check_test_direct_ctor() -> list[str]:
    violations: list[str] = []
    for py in sorted(TESTS_DIR.glob("test_*.py")):
        if py.name in TEST_CTOR_ALLOWLIST:
            continue
        for i, line in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
            if CTOR_PATTERN.match(line):
                rel = py.relative_to(ROOT).as_posix()
                violations.append(f"{rel}:{i}: direct Model(...) in test — use factory")
    return violations


def main() -> int:
    sections = [
        ("routes use db.query", _check_router_db_query()),
        ("services use request.session", _check_service_request_session()),
        ("tests use direct Model(...)", _check_test_direct_ctor()),
    ]
    total = sum(len(v) for _, v in sections)

    if total == 0:
        print("anti-pattern check: PASS (0 violations)")
        return 0

    print(f"anti-pattern check: FAIL ({total} violations)")
    for name, violations in sections:
        if violations:
            print(f"\n[{name}] {len(violations)}건")
            for v in violations:
                print(f"  {v}")
    print(
        "\nFix: move logic to service / pass User as arg / use factory. "
        "If legitimate exception, add file to ALLOWLIST in this script with reason."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
