from sqlalchemy.orm import Session

from app.models.region import Region


def test_create_region(db: Session) -> None:
    region = Region(
        sido="경기도",
        sigungu="양평군",
        slug="yangpyeong",
        is_pilot=True,
    )
    db.add(region)
    db.flush()

    assert region.id is not None
    assert region.is_pilot is True
    assert region.created_at is not None
