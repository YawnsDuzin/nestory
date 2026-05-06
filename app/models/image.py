from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._enums import ImageStatus


class Image(Base):
    __tablename__ = "images"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    post_id: Mapped[int | None] = mapped_column(
        ForeignKey("posts.id", ondelete="SET NULL"), nullable=True, index=True
    )

    file_path_orig: Mapped[str] = mapped_column(String(512))
    file_path_thumb: Mapped[str | None] = mapped_column(String(512), nullable=True)
    file_path_medium: Mapped[str | None] = mapped_column(String(512), nullable=True)
    file_path_webp: Mapped[str | None] = mapped_column(String(512), nullable=True)

    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    alt_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    order_idx: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    status: Mapped[ImageStatus] = mapped_column(
        Enum(ImageStatus, name="image_status", values_callable=lambda x: [e.value for e in x]),
        default=ImageStatus.PROCESSING,
        server_default=ImageStatus.PROCESSING.value,
    )

    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
