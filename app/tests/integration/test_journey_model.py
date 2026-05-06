from datetime import date

from sqlalchemy.orm import Session

from app.models import Journey
from app.models._enums import JourneyStatus
from app.tests.factories import RegionFactory, UserFactory


def test_create_journey_defaults_in_progress(db: Session) -> None:
    u = UserFactory()
    r = RegionFactory()
    j = Journey(author_id=u.id, region_id=r.id, title="우리 집 짓기")
    db.add(j)
    db.flush()

    assert j.id is not None
    assert j.status == JourneyStatus.IN_PROGRESS
    assert j.created_at is not None
    assert j.deleted_at is None


def test_journey_with_start_date_and_completed(db: Session) -> None:
    u = UserFactory()
    r = RegionFactory()
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
