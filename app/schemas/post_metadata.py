"""Pydantic Discriminated Union for Post.metadata validation.

Enforces schema integrity per Post.type. Used by all write routes
in P1.3+ (write_review, write_plan, journey episode, Q&A).

Reference: PRD §5.3 v1.1 [A3].
"""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PositiveInt


class _Forbid(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------- Pillar C 공통 sub-schema ----------

class RegretItem(_Forbid):
    category: Literal["land", "design", "build", "move", "life", "region"]
    cost_krw_band: Literal["<100", "100-500", "500-2000", "2000+"]
    time_months_band: Literal["<1", "1-3", "3-6", "6+"]
    free_text: str | None = Field(default=None, max_length=300)


class BudgetBreakdown(_Forbid):
    land: int = 0
    construction: int = 0
    etc: int = 0


class BuilderInfo(_Forbid):
    name: str
    verified: bool = False


class JourneyEpMeta(_Forbid):
    phase: Literal["터", "건축", "입주", "1년차", "3년차"]
    period_label: str = Field(max_length=40)


# ---------- Type별 메타데이터 ----------

class ReviewMetadata(_Forbid):
    type_tag: Literal["review"] = Field(alias="__post_type__", default="review")

    house_type: Literal["단독", "타운하우스", "듀플렉스"]
    size_pyeong: PositiveInt
    land_size_pyeong: PositiveInt | None = None
    budget_total_manwon: PositiveInt | None = None
    budget_breakdown: BudgetBreakdown | None = None
    move_in_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")
    construction_period_months: PositiveInt | None = None
    satisfaction_overall: int = Field(ge=1, le=5)
    regrets: list[str] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)
    builder_info: BuilderInfo | None = None
    regret_items: list[RegretItem] = Field(default_factory=list)
    review_year_offset: int = Field(ge=0, le=10, default=1)


class JourneyEpisodeMetadata(_Forbid):
    type_tag: Literal["journey_episode"] = Field(alias="__post_type__", default="journey_episode")
    journey_ep_meta: JourneyEpMeta


class QuestionMetadata(_Forbid):
    type_tag: Literal["question"] = Field(alias="__post_type__", default="question")
    tags: list[str] = Field(default_factory=list, max_length=10)


class AnswerMetadata(_Forbid):
    type_tag: Literal["answer"] = Field(alias="__post_type__", default="answer")


class PlanMetadata(_Forbid):
    type_tag: Literal["plan"] = Field(alias="__post_type__", default="plan")
    interest_regions: list[int] = Field(default_factory=list, max_length=10)
    target_move_year: int = Field(ge=2026, le=2050)
    household_size: PositiveInt = 1
    budget_total_manwon_band: Literal[
        "<5000", "5000-10000", "10000-20000", "20000-40000", "40000+"
    ]
    must_have: list[str] = Field(default_factory=list, max_length=10)
    nice_to_have: list[str] = Field(default_factory=list, max_length=10)
    concerns: list[str] = Field(default_factory=list, max_length=10)
    construction_intent: Literal["self_build", "buy_existing", "rent_first", "undecided"]
    open_to_advice: bool = True


PostMetadata = Annotated[
    ReviewMetadata | JourneyEpisodeMetadata | QuestionMetadata | AnswerMetadata | PlanMetadata,
    Field(discriminator="type_tag"),
]
