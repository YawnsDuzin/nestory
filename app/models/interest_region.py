from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, PrimaryKeyConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserInterestRegion(Base):
    __tablename__ = "user_interest_regions"
    __table_args__ = (PrimaryKeyConstraint("user_id", "region_id"),)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id", ondelete="CASCADE"), index=True)
    priority: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
