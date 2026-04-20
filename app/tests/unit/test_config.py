import os
from app.config import Settings


def test_settings_reads_env(monkeypatch):
    monkeypatch.setenv("APP_SECRET_KEY", "test-secret")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@h/d")
    monkeypatch.setenv("ADMIN_EMAIL", "admin@example.com")
    settings = Settings()
    assert settings.app_secret_key == "test-secret"
    assert settings.database_url == "postgresql+psycopg://u:p@h/d"
    assert settings.admin_email == "admin@example.com"
    assert settings.session_cookie_secure is False


def test_settings_derived_session_cookie_secure(monkeypatch):
    monkeypatch.setenv("APP_SECRET_KEY", "x")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@h/d")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "true")
    settings = Settings()
    assert settings.session_cookie_secure is True
