"""scripts/check_anti_patterns.py가 현 codebase에서 PASS 하는지 검증.

CLAUDE.md '안티패턴' 자동화의 회귀 가드. 신규 위반(routes의 db.query, services의
request.session, tests의 직접 Model 생성자)이 추가되면 이 테스트가 실패한다.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
SCRIPT = ROOT / "scripts" / "check_anti_patterns.py"


def test_anti_pattern_check_passes() -> None:
    result = subprocess.run(  # noqa: S603 — 자체 스크립트 실행
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert result.returncode == 0, (
        f"anti-pattern check failed:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
