"""Integration tests for /admin/users route."""
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.tests.factories import (
    AdminUserFactory,
    ResidentUserFactory,
    UserFactory,
)


def test_users_list_requires_admin(client: TestClient, db: Session, login) -> None:
    user = UserFactory()
    db.commit()
    login(user.id)
    r = client.get("/admin/users")
    assert r.status_code == 403


def test_users_list_renders(client: TestClient, db: Session, login) -> None:
    admin = AdminUserFactory()
    UserFactory(username="searchable_user")
    db.commit()
    login(admin.id)
    r = client.get("/admin/users")
    assert r.status_code == 200
    assert "사용자 조회" in r.text


def test_users_search_q_filters(client: TestClient, db: Session, login) -> None:
    admin = AdminUserFactory()
    UserFactory(username="alice_xyz", email="alice@x.com")
    UserFactory(username="bob_xyz", email="bob@x.com")
    db.commit()
    login(admin.id)
    r = client.get("/admin/users?q=alice")
    assert r.status_code == 200
    assert "alice_xyz" in r.text
    assert "bob_xyz" not in r.text


def test_users_filter_by_badge_level(client: TestClient, db: Session, login) -> None:
    admin = AdminUserFactory()
    UserFactory()
    ResidentUserFactory(username="resident_user")
    db.commit()
    login(admin.id)
    r = client.get("/admin/users?badge_level=resident")
    assert r.status_code == 200
    assert "resident_user" in r.text
