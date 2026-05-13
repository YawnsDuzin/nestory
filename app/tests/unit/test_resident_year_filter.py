"""Tests for resident_year Jinja filter."""
from datetime import UTC, datetime, timedelta

from app.templating_filters import resident_year


def test_resident_year_returns_empty_for_none():
    assert resident_year(None) == ""


def test_resident_year_returns_1nyeoncha_for_recently_verified():
    """0일 ~ 364일 = 1년차 (max(1, ...) clamp)."""
    now = datetime.now(UTC)
    assert resident_year(now) == "1년차"
    assert resident_year(now - timedelta(days=10)) == "1년차"
    assert resident_year(now - timedelta(days=200)) == "1년차"


def test_resident_year_returns_1nyeoncha_at_exactly_one_year():
    """365일 = 1년차 (365 // 365 = 1)."""
    now = datetime.now(UTC)
    assert resident_year(now - timedelta(days=365)) == "1년차"


def test_resident_year_returns_2nyeoncha_at_two_years():
    now = datetime.now(UTC)
    assert resident_year(now - timedelta(days=365 * 2)) == "2년차"


def test_resident_year_returns_5nyeoncha_at_five_years():
    now = datetime.now(UTC)
    assert resident_year(now - timedelta(days=365 * 5)) == "5년차"


def test_resident_year_handles_future_timestamp_as_1nyeoncha():
    """미래 시각(데이터 오류)은 음수 days → max(1, ...)로 1년차로 clamp."""
    now = datetime.now(UTC)
    assert resident_year(now + timedelta(days=30)) == "1년차"
