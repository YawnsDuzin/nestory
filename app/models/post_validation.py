from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._enums import ValidationVote


class PostValidation(Base):
    __tablename__ = "post_validations"
    __table_args__ = (
        UniqueConstraint("post_id", "validator_user_id", name="uq_post_validations_post_validator"),
        Index("ix_post_validations_post_vote", "post_id", "vote"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"))
    validator_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    vote: Mapped[ValidationVote] = mapped_column(
        Enum(ValidationVote, name="validation_vote", values_callable=lambda x: [e.value for e in x])
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
