"""Base for all model factories. Session is injected at runtime by conftest."""
from factory.alchemy import SQLAlchemyModelFactory


class BaseFactory(SQLAlchemyModelFactory):
    """Abstract base. `sqlalchemy_session` is set by `_bind_factories(db)` in conftest.

    `persistence="flush"` keeps factory-created rows uncommitted so the autouse
    `_cleanup_db` TRUNCATE CASCADE works correctly between tests.
    """

    class Meta:
        abstract = True
        sqlalchemy_session = None
        sqlalchemy_session_persistence = "flush"
