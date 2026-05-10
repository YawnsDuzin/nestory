import pytest

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


def test_production_requires_session_cookie_secure(monkeypatch):
    """prod에서 session_cookie_secure=False면 부팅 자체를 막는다 — cookie hijack 방어."""
    monkeypatch.setenv("APP_SECRET_KEY", "x")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@h/d")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "false")
    with pytest.raises(ValueError, match="session_cookie_secure must be true"):
        Settings()


def test_production_with_session_cookie_secure_passes(monkeypatch):
    monkeypatch.setenv("APP_SECRET_KEY", "x")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@h/d")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "true")
    settings = Settings()
    assert settings.app_env == "production"
    assert settings.session_cookie_secure is True


def test_local_env_allows_insecure_cookie(monkeypatch):
    """local·dev 환경은 secure=False 허용."""
    monkeypatch.setenv("APP_SECRET_KEY", "x")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@h/d")
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "false")
    settings = Settings()
    assert settings.session_cookie_secure is False
