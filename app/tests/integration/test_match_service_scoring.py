"""Integration tests for `compute_top_regions` deterministic scoring.

Tests:
- test_compute_returns_top_3_in_score_order
- test_same_input_yields_same_output
- test_invalid_answer_code_raises
- test_returns_at_most_3_even_with_more_regions
- test_resolves_ties_by_region_id_for_determinism

NOTE: Requires running Postgres (factory-boy uses test session).
"""
import pytest
from sqlalchemy.orm import Session

from app.services.match import compute_top_regions
from app.tests.factories import PilotRegionFactory, RegionScoringWeightFactory


def _seed_region(slug: str, sigungu: str, **scores) -> object:
    region = PilotRegionFactory(slug=slug, sigungu=sigungu)
    RegionScoringWeightFactory(region=region, **scores)
    return region


def test_compute_returns_top_3_in_score_order(db: Session) -> None:
    _seed_region(
        "high", "최고시",
        activity_score=10, medical_score=10, family_visit_score=10,
        farming_score=10, budget_score=10,
    )
    _seed_region(
        "mid", "중간시",
        activity_score=5, medical_score=5, family_visit_score=5,
        farming_score=5, budget_score=5,
    )
    _seed_region(
        "low", "낮음시",
        activity_score=1, medical_score=1, family_visit_score=1,
        farming_score=1, budget_score=1,
    )
    answers = {1: "A", 2: "A", 3: "A", 4: "A", 5: "A"}
    matches = compute_top_regions(db, answers)
    assert [m.region.slug for m in matches] == ["high", "mid", "low"]
    assert matches[0].total_score > matches[1].total_score > matches[2].total_score


def test_same_input_yields_same_output(db: Session) -> None:
    _seed_region("a", "에이시", activity_score=5, medical_score=5,
                 family_visit_score=5, farming_score=5, budget_score=5)
    _seed_region("b", "비이시", activity_score=6, medical_score=6,
                 family_visit_score=6, farming_score=6, budget_score=6)
    answers = {1: "B", 2: "C", 3: "B", 4: "B", 5: "C"}
    r1 = compute_top_regions(db, answers)
    r2 = compute_top_regions(db, answers)
    assert [m.region.slug for m in r1] == [m.region.slug for m in r2]
    assert [m.total_score for m in r1] == [m.total_score for m in r2]


def test_invalid_answer_code_raises(db: Session) -> None:
    with pytest.raises(ValueError, match="invalid answer"):
        compute_top_regions(db, {1: "A", 2: "A", 3: "A", 4: "A", 5: "Z"})


def test_returns_at_most_3_even_with_more_regions(db: Session) -> None:
    for i in range(5):
        _seed_region(f"r{i}", f"리전{i}",
                     activity_score=i, medical_score=i, family_visit_score=i,
                     farming_score=i, budget_score=i)
    matches = compute_top_regions(db, {1: "A", 2: "A", 3: "A", 4: "A", 5: "A"})
    assert len(matches) == 3


def test_resolves_ties_by_region_id_for_determinism(db: Session) -> None:
    a = _seed_region("aa", "에이에이시", activity_score=5, medical_score=5,
                     family_visit_score=5, farming_score=5, budget_score=5)
    b = _seed_region("bb", "비비시", activity_score=5, medical_score=5,
                     family_visit_score=5, farming_score=5, budget_score=5)
    matches = compute_top_regions(db, {1: "A", 2: "A", 3: "A", 4: "A", 5: "A"})
    # 동점 — region_id 오름차순 (a 먼저 생성 → id 작음)
    assert matches[0].region.id < matches[1].region.id
    assert matches[0].region.id == a.id
    assert matches[1].region.id == b.id


def test_empty_db_returns_empty_list(db: Session) -> None:
    """No RegionScoringWeight rows → empty list (route layer enforces ≥3 contract)."""
    matches = compute_top_regions(db, {1: "A", 2: "A", 3: "A", 4: "A", 5: "A"})
    assert matches == []


def test_returns_partial_when_fewer_than_3_regions(db: Session) -> None:
    """Service returns whatever is available; route layer enforces minimum."""
    _seed_region("only-a", "전부시", activity_score=5, medical_score=5,
                 family_visit_score=5, farming_score=5, budget_score=5)
    _seed_region("only-b", "유일시", activity_score=6, medical_score=6,
                 family_visit_score=6, farming_score=6, budget_score=6)
    matches = compute_top_regions(db, {1: "A", 2: "A", 3: "A", 4: "A", 5: "A"})
    assert len(matches) == 2
    assert matches[0].rank == 1
    assert matches[1].rank == 2


def test_missing_answer_raises(db: Session) -> None:
    with pytest.raises(ValueError, match="missing answer"):
        compute_top_regions(db, {1: "A", 2: "A", 3: "A", 4: "A"})  # no Q5
