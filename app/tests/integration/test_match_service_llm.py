"""Tests for match.generate_explanations — SDK mock + fallback.

Tests:
- test_returns_static_when_oauth_empty
- test_calls_sdk_per_match_and_returns_text
- test_falls_back_on_sdk_exception

NOTE: Requires running Postgres for factory rows.
"""
from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from app.services.match import (
    RegionMatch,
    generate_explanations,
)
from app.tests.factories import PilotRegionFactory, RegionScoringWeightFactory


def _make_match(db: Session, slug: str = "yang", rank: int = 1) -> RegionMatch:
    region = PilotRegionFactory(slug=slug, sigungu="양평군")
    weight = RegionScoringWeightFactory(region=region)
    return RegionMatch(region=region, weight=weight, total_score=200, rank=rank)


_ANSWERS = {1: "A", 2: "A", 3: "B", 4: "B", 5: "C"}


def test_returns_static_when_oauth_empty(db: Session) -> None:
    m = _make_match(db, "yang", 1)
    with patch("app.services.match.get_settings") as gs:
        gs.return_value = MagicMock(anthropic_oauth_token="")
        result = generate_explanations([m], _ANSWERS)
    assert len(result) == 1
    assert "양평" in result[0]
    assert "1" in result[0] or "추천" in result[0]


def test_calls_sdk_per_match_and_returns_text(db: Session) -> None:
    m1 = _make_match(db, "yang1", 1)
    m2 = _make_match(db, "yang2", 2)
    fake_msg = MagicMock()
    fake_msg.content = [MagicMock(text="이곳이 잘 맞습니다.")]
    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_msg
    with patch("app.services.match.get_settings") as gs, patch(
        "app.services.match._get_sdk_client"
    ) as get_client:
        gs.return_value = MagicMock(anthropic_oauth_token="tok")
        get_client.return_value = fake_client
        result = generate_explanations([m1, m2], _ANSWERS)
    assert result == ["이곳이 잘 맞습니다.", "이곳이 잘 맞습니다."]
    assert fake_client.messages.create.call_count == 2


def test_falls_back_on_sdk_exception(db: Session) -> None:
    m = _make_match(db, "yang", 1)
    fake_client = MagicMock()
    fake_client.messages.create.side_effect = RuntimeError("API down")
    with patch("app.services.match.get_settings") as gs, patch(
        "app.services.match._get_sdk_client"
    ) as get_client:
        gs.return_value = MagicMock(anthropic_oauth_token="tok")
        get_client.return_value = fake_client
        result = generate_explanations([m], _ANSWERS)
    assert len(result) == 1
    assert "양평" in result[0]  # static fallback contains region name
