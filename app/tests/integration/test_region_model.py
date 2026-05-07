from sqlalchemy.orm import Session

from app.tests.factories import RegionFactory


def test_create_region(db: Session) -> None:
    region = RegionFactory(
        sido="경기도",
        sigungu="양평군",
        slug="yangpyeong",
        is_pilot=True,
    )

    assert region.id is not None
    assert region.is_pilot is True
    assert region.created_at is not None
