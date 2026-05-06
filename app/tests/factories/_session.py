"""Session binding for factory-boy factories.

factories use `_session_factory()` as their `sqlalchemy_session_factory`.
The autouse `_bind_factories` fixture in conftest.py calls `bind_session(db)`
at the start of each test so factories use the same session as the test.
"""
from sqlalchemy.orm import Session

_session: Session | None = None


def bind_session(s: Session) -> None:
    global _session
    _session = s


def _session_factory() -> Session:
    if _session is None:
        raise RuntimeError(
            "factory-boy session not bound. "
            "Ensure the _bind_factories autouse fixture runs."
        )
    return _session
