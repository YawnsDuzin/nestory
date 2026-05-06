from sqlalchemy import Column, ForeignKey, PrimaryKeyConstraint, String, Table
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

post_tags = Table(
    "post_tags",
    Base.metadata,
    Column("post_id", ForeignKey("posts.id", ondelete="CASCADE"), nullable=False),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), nullable=False),
    PrimaryKeyConstraint("post_id", "tag_id"),
)


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
