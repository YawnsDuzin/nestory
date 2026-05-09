"""Tests for analytics service — _distinct_id + emit branching."""
from unittest.mock import MagicMock, patch

from app.services.analytics import EventName, _distinct_id, emit


def test_distinct_id_deterministic_for_same_user() -> None:
    assert _distinct_id(123) == _distinct_id(123)


def test_distinct_id_different_for_different_users() -> None:
    assert _distinct_id(1) != _distinct_id(2)


def test_distinct_id_uses_sha256_for_user() -> None:
    out = _distinct_id(42)
    assert out == "73475cb40a568e8da8a045ced110137e159f890ac4da883b6b17dc651b3a8049"


def test_distinct_id_returns_anon_id_when_user_none() -> None:
    assert _distinct_id(None, "anon-abc") == "anon-abc"


def test_distinct_id_generates_anon_when_both_none() -> None:
    out = _distinct_id(None)
    assert out.startswith("anon-")
    assert len(out) > len("anon-")


def test_emit_noop_when_app_env_not_production() -> None:
    with patch("app.services.analytics._get_client") as get_client:
        emit(EventName.USER_LOGGED_IN)
        get_client.assert_not_called()


def test_emit_noop_when_api_key_empty() -> None:
    fake_settings = MagicMock(app_env="production", posthog_api_key="")
    with patch("app.services.analytics.get_settings", return_value=fake_settings):
        emit(EventName.USER_LOGGED_IN)


def test_emit_calls_capture_when_production_and_key_set() -> None:
    fake_settings = MagicMock(app_env="production", posthog_api_key="phc_xxx")
    fake_client = MagicMock()
    with patch("app.services.analytics.get_settings", return_value=fake_settings), patch(
        "app.services.analytics._get_client", return_value=fake_client
    ):
        emit(EventName.USER_LOGGED_IN, distinct_id_hash="hash123", props={"foo": "bar"})
    fake_client.capture.assert_called_once_with(
        distinct_id="hash123",
        event="user_logged_in",
        properties={"foo": "bar"},
    )


def test_emit_handles_capture_exception_gracefully() -> None:
    fake_settings = MagicMock(app_env="production", posthog_api_key="phc_xxx")
    fake_client = MagicMock()
    fake_client.capture.side_effect = RuntimeError("network down")
    with patch("app.services.analytics.get_settings", return_value=fake_settings), patch(
        "app.services.analytics._get_client", return_value=fake_client
    ):
        emit(EventName.USER_LOGGED_IN)


def test_emit_uses_anon_id_when_distinct_id_missing() -> None:
    fake_settings = MagicMock(app_env="production", posthog_api_key="phc_xxx")
    fake_client = MagicMock()
    with patch("app.services.analytics.get_settings", return_value=fake_settings), patch(
        "app.services.analytics._get_client", return_value=fake_client
    ):
        emit(EventName.USER_LOGGED_IN)
    args = fake_client.capture.call_args
    assert args.kwargs["distinct_id"].startswith("anon-")
