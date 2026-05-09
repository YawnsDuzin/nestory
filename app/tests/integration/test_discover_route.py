"""Integration tests for GET /discover — region grid page.

Tests:
- test_discover_returns_200_with_regions
- test_discover_orders_pilot_first
- test_discover_anonymous_user_works

NOTE: Requires a running Postgres instance.
      Cannot be executed on a no-Docker PC — run on docker-up PC.
"""
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.tests.factories import PilotRegionFactory, RegionFactory


def test_discover_returns_200_with_regions(client: TestClient, db: Session) -> None:
    """GET /discover returns 200 and lists all region sigungu names."""
    r1 = RegionFactory(sido="경기도", sigungu="양평군", is_pilot=False)
    r2 = RegionFactory(sido="전라남도", sigungu="곡성군", is_pilot=False)
    r3 = PilotRegionFactory(sido="경기도", sigungu="가평군")
    db.commit()

    r = client.get("/discover")
    assert r.status_code == 200
    assert r1.sigungu in r.text
    assert r2.sigungu in r.text
    assert r3.sigungu in r.text


def test_discover_orders_pilot_first(client: TestClient, db: Session) -> None:
    """Pilot regions must appear before non-pilot regions in /discover."""
    RegionFactory(sido="전라남도", sigungu="곡성군", is_pilot=False)
    PilotRegionFactory(sido="경기도", sigungu="양평군")
    db.commit()

    r = client.get("/discover")
    assert r.status_code == 200
    # Pilot region must appear earlier in the response text
    idx_pilot = r.text.index("양평군")
    idx_normal = r.text.index("곡성군")
    assert idx_pilot < idx_normal


def test_discover_anonymous_user_works(client: TestClient, db: Session) -> None:
    """GET /discover without a session cookie must return 200 (no auth required)."""
    RegionFactory(sido="강원도", sigungu="춘천시", is_pilot=False)
    db.commit()

    r = client.get("/discover")
    assert r.status_code == 200
