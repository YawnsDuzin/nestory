"""Region service — read-only helpers."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Region


def list_all_for_dropdown(db: Session) -> list[Region]:
    """전체 region을 sigungu alphabetical로 — write 폼 region 셀렉터용."""
    return list(db.scalars(select(Region).order_by(Region.sigungu)).all())


__all__ = ["list_all_for_dropdown"]
