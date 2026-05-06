"""Job handler registry.

Each handler module decorates its callable with `@register(JobKind.X)`.
`import_handlers()` imports all modules so decorators run.
`dispatch(kind, payload)` invokes the matching handler — raises if missing.
"""
from collections.abc import Callable
from typing import Any

import structlog

from app.models._enums import JobKind

log = structlog.get_logger(__name__)
Handler = Callable[[dict[str, Any]], None]
_REGISTRY: dict[JobKind, Handler] = {}


def register(kind: JobKind) -> Callable[[Handler], Handler]:
    def deco(fn: Handler) -> Handler:
        if kind in _REGISTRY:
            raise RuntimeError(f"Handler for {kind.value} already registered")
        _REGISTRY[kind] = fn
        return fn
    return deco


def dispatch(kind: JobKind, payload: dict[str, Any]) -> None:
    handler = _REGISTRY.get(kind)
    if handler is None:
        raise RuntimeError(f"No handler registered for {kind.value}")
    handler(payload)


def registered_kinds() -> set[JobKind]:
    return set(_REGISTRY.keys())


def import_handlers() -> None:
    """Import all handler modules so decorators register them."""
    from app.workers.handlers import (  # noqa: F401
        evidence_cleanup,
        image_resize,
        notification,
    )
