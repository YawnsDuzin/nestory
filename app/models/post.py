from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._enums import PostStatus, PostType


class Post(Base):
    __tablename__ = "posts"
    __table_args__ = (
        Index("ix_posts_region_published", "region_id", "published_at"),
        Index("ix_posts_journey_episode", "journey_id", "episode_no"),
        Index("ix_posts_author_published", "author_id", "published_at"),
        Index("ix_posts_type_status_published", "type", "status", "published_at"),
        Index("ix_posts_metadata_gin", "metadata", postgresql_using="gin"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id", ondelete="RESTRICT"))
    journey_id: Mapped[int | None] = mapped_column(
        ForeignKey("journeys.id", ondelete="SET NULL"), nullable=True
    )
    parent_post_id: Mapped[int | None] = mapped_column(
        ForeignKey("posts.id", ondelete="SET NULL"), nullable=True
    )

    type: Mapped[PostType] = mapped_column(
        Enum(PostType, name="post_type", values_callable=lambda x: [e.value for e in x])
    )
    episode_no: Mapped[int | None] = mapped_column(Integer, nullable=True)

    title: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, default=dict, server_default="{}"
    )

    status: Mapped[PostStatus] = mapped_column(
        Enum(PostStatus, name="post_status", values_callable=lambda x: [e.value for e in x]),
        default=PostStatus.DRAFT,
        server_default=PostStatus.DRAFT.value,
    )
    view_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
