import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import UserInterestRegion
from app.tests.factories import RegionFactory, UserFactory, UserInterestRegionFactory


def test_user_can_have_multiple_interest_regions(db: Session) -> None:
    u = UserFactory()
    r1 = RegionFactory(slug="yangpyeong-test")
    r2 = RegionFactory(slug="gapyeong-test")
    UserInterestRegionFactory(user=u, region=r1, priority=1)
    UserInterestRegionFactory(user=u, region=r2, priority=2)

    rows = (
        db.query(UserInterestRegion)
        .filter_by(user_id=u.id)
        .order_by(UserInterestRegion.priority)
        .all()
    )
    assert [r.region_id for r in rows] == [r1.id, r2.id]


def test_duplicate_user_region_pair_rejected(db: Session) -> None:
    u = UserFactory()
    r = RegionFactory(slug="yangpyeong-test")
    UserInterestRegionFactory(user=u, region=r, priority=1)
    db.add(UserInterestRegion(user_id=u.id, region_id=r.id, priority=2))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()
