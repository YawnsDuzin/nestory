"""E2E flow: 5문항 → submit → result. UPSERT 검증.

비로그인 + 로그인 두 시나리오. LLM은 OAuth 빈값 fallback 사용.

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
)


def _seed_4(db: Session) -> None:
    for slug, sigungu, scores in [
        ("yang2", "양평군", (8, 7, 9, 7, 6)),
        ("gap2",  "가평군", (8, 5, 8, 8, 7)),
        ("chu2",  "춘천시", (7, 8, 6, 6, 7)),
        ("hong2", "홍성군", (6, 6, 5, 9, 9)),
    ]:
        r = PilotRegionFactory(slug=slug, sigungu=sigungu)
        a, m, fv, fa, b = scores
        RegionScoringWeightFactory(
            region=r, activity_score=a, medical_score=m,
            family_visit_score=fv, farming_score=fa, budget_score=b,
        )


def _patch_oauth_empty():
    return patch(
        "app.services.match.get_settings",
        return_value=MagicMock(anthropic_oauth_token=""),
    )


def test_full_anonymous_flow(client: TestClient, db: Session) -> None:
    _seed_4(db)
    db.commit()  # 라우트의 별도 세션이 seed를 보려면 commit 필요
    assert client.get("/match/wizard").status_code == 200
    for n in range(1, 6):
        assert client.get(f"/match/wizard/q/{n}").status_code == 200
    with _patch_oauth_empty():
        r = client.post(
            "/match/wizard/submit",
            data={"a1": "A", "a2": "A", "a3": "A", "a4": "A", "a5": "A"},
            follow_redirects=True,
        )
    assert r.status_code == 200
    visible = sum(1 for s in ("양평군", "가평군", "춘천시", "홍성군") if s in r.text)
    assert visible >= 3


def test_full_logged_in_flow_persists_top_3(
    client: TestClient, db: Session, login
) -> None:
    _seed_4(db)
    user = UserFactory()
    db.commit()
    login(user.id)
    with _patch_oauth_empty():
        r = client.post(
            "/match/wizard/submit",
            data={"a1": "B", "a2": "B", "a3": "B", "a4": "B", "a5": "B"},
            follow_redirects=True,
        )
    assert r.status_code == 200
    rows = list(
        db.scalars(
            select(UserInterestRegion)
            .where(UserInterestRegion.user_id == user.id)
            .order_by(UserInterestRegion.priority)
        ).all()
    )
    assert [row.priority for row in rows] == [1, 2, 3]
