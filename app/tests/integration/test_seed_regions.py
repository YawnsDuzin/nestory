from sqlalchemy.orm import Session

from app.models.region import Region
from scripts.seed_regions import PILOT_REGIONS, seed_regions


def test_seed_regions_inserts_pilot_set(db: Session) -> None:
    seed_regions(db)
    db.commit()

    rows = db.query(Region).all()
    assert len(rows) == len(PILOT_REGIONS)

    slugs = {r.slug for r in rows}
    assert {"yangpyeong", "gapyeong", "namyangju", "chuncheon", "hongcheon"} <= slugs
    assert all(r.is_pilot for r in rows)


def test_seed_regions_is_idempotent(db: Session) -> None:
    seed_regions(db)
    db.commit()
    seed_regions(db)
    db.commit()

    count = db.query(Region).count()
    assert count == len(PILOT_REGIONS)
