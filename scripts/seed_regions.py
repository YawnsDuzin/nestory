"""파일럿 5개 시군을 regions 테이블에 주입 (idempotent).

OI-1 잠정 가정: 양평 · 가평 · 남양주 · 춘천 · 홍천.
Phase 0 중 최종 결정되면 이 목록을 갱신할 것.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.region import Region

PILOT_REGIONS: list[dict[str, str]] = [
    {"sido": "경기도", "sigungu": "양평군", "slug": "yangpyeong"},
    {"sido": "경기도", "sigungu": "가평군", "slug": "gapyeong"},
    {"sido": "경기도", "sigungu": "남양주시", "slug": "namyangju"},
    {"sido": "강원특별자치도", "sigungu": "춘천시", "slug": "chuncheon"},
    {"sido": "강원특별자치도", "sigungu": "홍천군", "slug": "hongcheon"},
]


def seed_regions(db: Session) -> None:
    existing_slugs = {slug for (slug,) in db.query(Region.slug).all()}
    for row in PILOT_REGIONS:
        if row["slug"] in existing_slugs:
            continue
        db.add(Region(
            sido=row["sido"],
            sigungu=row["sigungu"],
            slug=row["slug"],
            is_pilot=True,
        ))


def main() -> None:
    db = SessionLocal()
    try:
        seed_regions(db)
        db.commit()
        print(f"Seeded {len(PILOT_REGIONS)} pilot regions (idempotent).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
