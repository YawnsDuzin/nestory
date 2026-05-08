from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RegionScoringWeight(Base):
    __tablename__ = "region_scoring_weights"

    region_id: Mapped[int] = mapped_column(
        ForeignKey("regions.id", ondelete="CASCADE"), primary_key=True
    )
    activity_score: Mapped[int] = mapped_column(Integer)
    medical_score: Mapped[int] = mapped_column(Integer)
    family_visit_score: Mapped[int] = mapped_column(Integer)
    farming_score: Mapped[int] = mapped_column(Integer)
    budget_score: Mapped[int] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    updated_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
