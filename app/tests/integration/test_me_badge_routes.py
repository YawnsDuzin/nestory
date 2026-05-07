import io

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import BadgeApplication
from app.tests.factories import RegionFactory, UserFactory


def test_badge_page_requires_login(client: TestClient) -> None:
    r = client.get("/me/badge")
    assert r.status_code == 401


def test_badge_page_renders_for_logged_in_user(
    db: Session, client: TestClient, login,
) -> None:
    user = UserFactory()
    db.commit()
    login(user.id)
    r = client.get("/me/badge")
    assert r.status_code == 200
    assert "내 배지" in r.text
    assert "관심자" in r.text  # 기본 배지 표시


def test_apply_region_creates_pending_application(
    db: Session, client: TestClient, login,
) -> None:
    user = UserFactory()
    region = RegionFactory(slug="yp-me-test")
    db.commit()

    login(user.id)
    r = client.post("/me/badge/region", data={"region_id": region.id}, follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/me/badge"

    apps = db.query(BadgeApplication).filter_by(user_id=user.id).all()
    assert len(apps) == 1
    assert apps[0].region_id == region.id


def test_apply_region_blocks_duplicate_pending(
    db: Session, client: TestClient, login,
) -> None:
    user = UserFactory()
    region = RegionFactory(slug="yp-dup")
    db.commit()
    login(user.id)
    client.post("/me/badge/region", data={"region_id": region.id})
    r = client.post("/me/badge/region", data={"region_id": region.id})
    assert r.status_code == 409


def test_apply_region_invalid_id(db: Session, client: TestClient, login) -> None:
    user = UserFactory()
    db.commit()
    login(user.id)
    r = client.post("/me/badge/region", data={"region_id": 99999})
    assert r.status_code == 400


def test_resident_form_renders(db: Session, client: TestClient, login) -> None:
    user = UserFactory()
    db.commit()
    login(user.id)
    r = client.get("/me/badge/resident")
    assert r.status_code == 200
    assert "실거주자 인증" in r.text


def test_resident_apply_with_one_evidence(
    db: Session, client: TestClient, login, tmp_path, monkeypatch,
) -> None:
    monkeypatch.setenv("EVIDENCE_BASE_PATH", str(tmp_path / "evidence"))
    from app.config import get_settings
    get_settings.cache_clear()

    user = UserFactory()
    region = RegionFactory(slug="yp-resident")
    db.commit()
    login(user.id)

    files = {"utility_bill": ("bill.jpg", io.BytesIO(b"fake"), "image/jpeg")}
    r = client.post(
        "/me/badge/resident",
        data={"region_id": region.id},
        files=files,
        follow_redirects=False,
    )
    assert r.status_code == 303

    apps = db.query(BadgeApplication).filter_by(user_id=user.id).all()
    assert len(apps) == 1
    assert apps[0].requested_level.value == "resident"
    from app.models import BadgeEvidence
    es = db.query(BadgeEvidence).filter_by(application_id=apps[0].id).all()
    assert len(es) == 1


def test_resident_apply_rejects_no_evidence(
    db: Session, client: TestClient, login,
) -> None:
    user = UserFactory()
    region = RegionFactory(slug="yp-no-ev")
    db.commit()
    login(user.id)
    r = client.post("/me/badge/resident", data={"region_id": region.id})
    assert r.status_code == 400
