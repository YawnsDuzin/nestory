"""Integration tests for /match/* routes.

Tests:
- test_wizard_start_returns_200
- test_wizard_question_n_returns_partial
- test_wizard_question_invalid_n_returns_404
- test_submit_redirects_to_result_with_query_string
- test_submit_invalid_answer_returns_400
- test_result_with_full_answers_returns_200
- test_result_missing_answers_redirects_to_wizard
- test_result_logged_in_upserts_user_interest_regions
- test_result_logged_in_preserves_manual_interest_regions
- test_result_logged_in_rerun_updates_existing_region_priority

NOTE: Requires a running Postgres instance.
      Cannot be executed on a no-Docker PC — run on docker-up PC.
"""
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import UserInterestRegion
from app.tests.factories import (
    PilotRegionFactory,
    RegionScoringWeightFactory,
    UserFactory,
    UserInterestRegionFactory,
)


def _seed_4_regions(db: Session) -> None:
    """4 pilot region with weights — required for result page (>=3)."""
    for slug, sigungu, scores in [
        ("yang", "양평군", (8, 7, 9, 7, 6)),
        ("gap",  "가평군", (8, 5, 8, 8, 7)),
        ("chu",  "춘천시", (7, 8, 6, 6, 7)),
        ("hong", "홍성군", (6, 6, 5, 9, 9)),
    ]:
        region = PilotRegionFactory(slug=slug, sigungu=sigungu)
        a, m, fv, fa, b = scores
        RegionScoringWeightFactory(
            region=region,
            activity_score=a, medical_score=m, family_visit_score=fv,
            farming_score=fa, budget_score=b,
        )


def _patch_oauth_empty():
    """patch ctx — `match.get_settings()`가 OAuth 빈값 객체 반환. fallback 강제."""
    return patch(
        "app.services.match.get_settings",
        return_value=MagicMock(anthropic_oauth_token=""),
    )


def test_wizard_start_returns_200(client: TestClient) -> None:
    r = client.get("/match/wizard")
    assert r.status_code == 200
    assert "시군 찾기" in r.text


def test_wizard_question_n_returns_partial(client: TestClient) -> None:
    r = client.get("/match/wizard/q/1")
    assert r.status_code == 200
    assert "텃밭" in r.text  # Q1 옵션 A


def test_wizard_question_invalid_n_returns_404(client: TestClient) -> None:
    assert client.get("/match/wizard/q/0").status_code == 404
    assert client.get("/match/wizard/q/6").status_code == 404


def test_submit_redirects_to_result_with_query_string(client: TestClient) -> None:
    r = client.post(
        "/match/wizard/submit",
        data={"a1": "A", "a2": "A", "a3": "A", "a4": "A", "a5": "A"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"].startswith("/match/result?")
    for n in range(1, 6):
        assert f"a{n}=A" in r.headers["location"]


def test_submit_invalid_answer_returns_400(client: TestClient) -> None:
    r = client.post(
        "/match/wizard/submit",
        data={"a1": "Z", "a2": "A", "a3": "A", "a4": "A", "a5": "A"},
    )
    assert r.status_code == 400


def test_result_with_full_answers_returns_200(
    client: TestClient, db: Session
) -> None:
    _seed_4_regions(db)
    with _patch_oauth_empty():
        r = client.get("/match/result?a1=A&a2=A&a3=A&a4=A&a5=A")
    assert r.status_code == 200
    assert any(s in r.text for s in ("양평", "가평", "춘천", "홍성"))


def test_result_missing_answers_redirects_to_wizard(client: TestClient) -> None:
    r = client.get("/match/result?a1=A&a2=A", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/match/wizard"


def test_result_logged_in_upserts_user_interest_regions(
    client: TestClient, db: Session, login
) -> None:
    _seed_4_regions(db)
    user = UserFactory()
    login(user.id)
    with _patch_oauth_empty():
        r = client.get("/match/result?a1=A&a2=A&a3=A&a4=A&a5=A")
    assert r.status_code == 200
    rows = list(
        db.scalars(
            select(UserInterestRegion).where(UserInterestRegion.user_id == user.id)
        ).all()
    )
    assert len(rows) == 3
    assert {r.priority for r in rows} == {1, 2, 3}


def test_result_logged_in_preserves_manual_interest_regions(
    client: TestClient, db: Session, login
) -> None:
    """Wizard ON CONFLICT upsert는 wizard Top 3에 없는 manual region을 보존한다."""
    _seed_4_regions(db)
    user = UserFactory()
    # 사용자가 수동으로 추가한 priority=4 region (wizard Top 3와 무관)
    extra = PilotRegionFactory(slug="extra", sigungu="추가시")
    UserInterestRegionFactory(user=user, region=extra, priority=4)
    login(user.id)
    with _patch_oauth_empty():
        r = client.get("/match/result?a1=A&a2=A&a3=A&a4=A&a5=A")
    assert r.status_code == 200
    rows = list(
        db.scalars(
            select(UserInterestRegion).where(UserInterestRegion.user_id == user.id)
        ).all()
    )
    # 4 row total — wizard Top 3 (priority 1/2/3) + 사용자 manual extra (priority 4)
    assert len(rows) == 4
    assert extra.id in {r.region_id for r in rows}
    by_region = {r.region_id: r.priority for r in rows}
    assert by_region[extra.id] == 4  # manual row 그대로 유지


def test_result_logged_in_rerun_updates_existing_region_priority(
    client: TestClient, db: Session, login
) -> None:
    """Wizard 재실행 시 기존 wizard 결과 row가 새 priority로 갱신된다."""
    _seed_4_regions(db)
    user = UserFactory()
    login(user.id)
    with _patch_oauth_empty():
        client.get("/match/result?a1=A&a2=A&a3=A&a4=A&a5=A")
    # 다른 답변으로 재실행 — 같은 4 region, 다른 score sort → priority 재배치
    with _patch_oauth_empty():
        r = client.get("/match/result?a1=D&a2=D&a3=D&a4=D&a5=D")
    assert r.status_code == 200
    rows = list(
        db.scalars(
            select(UserInterestRegion).where(UserInterestRegion.user_id == user.id)
        ).all()
    )
    # 여전히 3 row (재실행 결과만) — 동일 region이라면 priority만 갱신
    assert len(rows) == 3
    assert {r.priority for r in rows} == {1, 2, 3}
