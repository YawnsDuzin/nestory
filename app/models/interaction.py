from sqlalchemy import Column, DateTime, ForeignKey, PrimaryKeyConstraint, Table, func

from app.db.base import Base

# 명시적 정의로 가독성 우선 — 헬퍼 사용 안 함
post_likes = Table(
    "post_likes",
    Base.metadata,
    Column("post_id", ForeignKey("posts.id", ondelete="CASCADE"), nullable=False),
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    PrimaryKeyConstraint("post_id", "user_id"),
)

post_scraps = Table(
    "post_scraps",
    Base.metadata,
    Column("post_id", ForeignKey("posts.id", ondelete="CASCADE"), nullable=False),
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    PrimaryKeyConstraint("post_id", "user_id"),
)

user_follows = Table(
    "user_follows",
    Base.metadata,
    Column("follower_id", ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("following_id", ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    PrimaryKeyConstraint("follower_id", "following_id"),
)

journey_follows = Table(
    "journey_follows",
    Base.metadata,
    Column("journey_id", ForeignKey("journeys.id", ondelete="CASCADE"), nullable=False),
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    PrimaryKeyConstraint("journey_id", "user_id"),
)
