import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas.post_metadata import (
    PlanMetadata,
    PostMetadata,
    ReviewMetadata,
)

post_meta_adapter = TypeAdapter(PostMetadata)


def test_review_metadata_minimal_valid() -> None:
    m = ReviewMetadata(
        __post_type__="review",
        house_type="단독",
        size_pyeong=32,
        satisfaction_overall=4,
    )
    assert m.satisfaction_overall == 4
    assert m.review_year_offset == 1


def test_review_rejects_extra_field() -> None:
    with pytest.raises(ValidationError) as exc:
        ReviewMetadata(
            __post_type__="review",
            house_type="단독",
            size_pyeong=32,
            satisfaction_overall=4,
            evil_field="injection",
        )
    assert "evil_field" in str(exc.value)


def test_review_rejects_invalid_satisfaction() -> None:
    with pytest.raises(ValidationError):
        ReviewMetadata(
            __post_type__="review",
            house_type="단독",
            size_pyeong=32,
            satisfaction_overall=99,
        )


def test_plan_metadata_minimal_valid() -> None:
    m = PlanMetadata(
        __post_type__="plan",
        target_move_year=2027,
        budget_total_manwon_band="10000-20000",
        construction_intent="undecided",
    )
    assert m.target_move_year == 2027


def test_discriminator_routes_to_correct_schema() -> None:
    parsed = post_meta_adapter.validate_python({
        "__post_type__": "plan",
        "target_move_year": 2027,
        "budget_total_manwon_band": "10000-20000",
        "construction_intent": "undecided",
    })
    assert isinstance(parsed, PlanMetadata)


def test_regret_item_band_validation() -> None:
    m = ReviewMetadata(
        __post_type__="review",
        house_type="단독",
        size_pyeong=32,
        satisfaction_overall=3,
        regret_items=[
            {
                "category": "land",
                "cost_krw_band": "500-2000",
                "time_months_band": "1-3",
                "free_text": "진입로 포장 추가 비용",
            }
        ],
    )
    assert m.regret_items[0].category == "land"

    with pytest.raises(ValidationError):
        ReviewMetadata(
            __post_type__="review",
            house_type="단독",
            size_pyeong=32,
            satisfaction_overall=3,
            regret_items=[
                {
                    "category": "INVALID",
                    "cost_krw_band": "<100",
                    "time_months_band": "<1",
                }
            ],
        )
