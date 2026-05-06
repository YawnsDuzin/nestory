from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from app.models import Journey, Region, User
from app.models._enums import JourneyStatus


def _seed(db: Session) -> tuple[User, Region]:
    u = User(
        email=f"t{int(datetime.now(UTC).timestamp() * 1_000_000)}@example.com",
        username=f"u{int(datetime.now(UTC).timestamp() * 1_000_000)}",
        display_name="테스터",
        password_hash="x",
    )
    r = Region(sido="경기", sigungu="양평군", slug=f"yp-{u.username}")
    db.add_all([u, r])
    db.flush()
    return u, r


def test_create_journey_defaults_in_progress(db: Session) -> None:
    u, r = _seed(db)
    j = Journey(author_id=u.id, region_id=r.id, title="우리 집 짓기")
    db.add(j)
    db.flush()

    assert j.id is not None
    assert j.status == JourneyStatus.IN_PROGRESS
    assert j.created_at is not None
    assert j.deleted_at is None


def test_journey_with_start_date_and_completed(db: Session) -> None:
    u, r = _seed(db)
    j = Journey(
        author_id=u.id,
        region_id=r.id,
        title="3년차 회고",
        start_date=date(2023, 4, 1),
        status=JourneyStatus.COMPLETED,
    )
    db.add(j)
    db.flush()
    assert j.start_date == date(2023, 4, 1)
    assert j.status == JourneyStatus.COMPLETED
