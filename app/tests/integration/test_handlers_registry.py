import pytest

from app.models._enums import JobKind
from app.workers.handlers import dispatch, import_handlers, registered_kinds


def test_import_handlers_registers_phase11_stubs() -> None:
    import_handlers()
    kinds = registered_kinds()
    assert JobKind.IMAGE_RESIZE in kinds
    assert JobKind.NOTIFICATION in kinds


def test_dispatch_invokes_registered_handler(caplog) -> None:
    import_handlers()
    # Should not raise; structlog goes to default logger.
    dispatch(JobKind.IMAGE_RESIZE, {"image_id": 99})


def test_dispatch_unknown_kind_raises() -> None:
    import_handlers()
    with pytest.raises(RuntimeError, match="No handler registered"):
        dispatch(JobKind.REVALIDATION_CHECK, {})
