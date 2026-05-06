from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._enums import (
    BadgeApplicationStatus,
    BadgeRequestedLevel,
    EvidenceType,
)


class BadgeApplication(Base):
    __tablename__ = "badge_applications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    requested_level: Mapped[BadgeRequestedLevel] = mapped_column(
        Enum(BadgeRequestedLevel, name="badge_requested_level",
             values_callable=lambda x: [e.value for e in x])
    )
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id", ondelete="RESTRICT"))
    status: Mapped[BadgeApplicationStatus] = mapped_column(
        Enum(BadgeApplicationStatus, name="badge_application_status",
             values_callable=lambda x: [e.value for e in x]),
        default=BadgeApplicationStatus.PENDING,
        server_default=BadgeApplicationStatus.PENDING.value,
        index=True,
    )
    reviewer_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BadgeEvidence(Base):
    __tablename__ = "badge_evidence"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("badge_applications.id", ondelete="CASCADE"), index=True
    )
    evidence_type: Mapped[EvidenceType] = mapped_column(
        Enum(EvidenceType, name="evidence_type",
             values_callable=lambda x: [e.value for e in x])
    )
    file_path: Mapped[str] = mapped_column(String(512))
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    scheduled_delete_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
