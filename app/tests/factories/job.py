"""Job factory (background queue)."""
import factory

from app.models import Job
from app.models._enums import JobKind, JobStatus
from app.tests.factories._base import BaseFactory


class JobFactory(BaseFactory):
    class Meta:
        model = Job

    kind = JobKind.NOTIFICATION
    payload = factory.LazyFunction(dict)
    status = JobStatus.QUEUED
