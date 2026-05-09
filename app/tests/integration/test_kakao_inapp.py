"""Tests for is_kakao_inapp UA detection."""
from unittest.mock import MagicMock

from app.services.kakao_inapp import is_kakao_inapp


def _request_with_ua(ua: str) -> MagicMock:
    req = MagicMock()
    req.headers = {"user-agent": ua}
    return req


def test_kakao_ua_detected() -> None:
    assert is_kakao_inapp(_request_with_ua("Mozilla/5.0 KAKAOTALK 9.0.0")) is True


def test_kakao_ua_lowercase_detected() -> None:
    assert is_kakao_inapp(_request_with_ua("kakaotalk/8.0")) is True


def test_chrome_ua_not_detected() -> None:
    assert is_kakao_inapp(
        _request_with_ua("Mozilla/5.0 (Windows NT 10) Chrome/120")
    ) is False


def test_empty_ua_not_detected() -> None:
    assert is_kakao_inapp(_request_with_ua("")) is False


def test_missing_ua_header_not_detected() -> None:
    req = MagicMock()
    req.headers = {}
    assert is_kakao_inapp(req) is False
