from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models import Region, User, UserInterestRegion


def _make_user(db: Session) -> User:
    u = User(
        email=f"t{int(datetime.now(UTC).timestamp() * 1_000_000)}@example.com",
        username=f"u{int(datetime.now(UTC).timestamp() * 1_000_000)}",
        display_name="테스터",
        password_hash="x",
    )
    db.add(u)
    db.flush()
    return u


def _make_region(db: Session, slug: str) -> Region:
    r = Region(sido="경기", sigungu="양평군", slug=slug)
    db.add(r)
    db.flush()
    return r


def test_user_can_have_multiple_interest_regions(db: Session) -> None:
    u = _make_user(db)
    r1 = _make_region(db, "yangpyeong-test")
    r2 = _make_region(db, "gapyeong-test")
    db.add(UserInterestRegion(user_id=u.id, region_id=r1.id, priority=1))
    db.add(UserInterestRegion(user_id=u.id, region_id=r2.id, priority=2))
    db.flush()

    rows = (
        db.query(UserInterestRegion)
        .filter_by(user_id=u.id)
        .order_by(UserInterestRegion.priority)
        .all()
    )
    assert [r.region_id for r in rows] == [r1.id, r2.id]


def test_duplicate_user_region_pair_rejected(db: Session) -> None:
    import pytest
    from sqlalchemy.exc import IntegrityError

    u = _make_user(db)
    r = _make_region(db, "yangpyeong-test")
    db.add(UserInterestRegion(user_id=u.id, region_id=r.id, priority=1))
    db.flush()
    db.add(UserInterestRegion(user_id=u.id, region_id=r.id, priority=2))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()
