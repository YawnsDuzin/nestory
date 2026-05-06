import json

import structlog

from app.logging_setup import configure_logging


def test_configure_logging_produces_json(capfd) -> None:
    configure_logging(env="production")
    log = structlog.get_logger("test")
    log.info("hello", user_id=42)

    captured = capfd.readouterr()
    line = captured.out.strip().splitlines()[-1]
    parsed = json.loads(line)
    assert parsed["event"] == "hello"
    assert parsed["user_id"] == 42
    assert parsed["level"] == "info"


def test_configure_logging_local_is_readable(capfd) -> None:
    configure_logging(env="local")
    log = structlog.get_logger("test")
    log.info("local-event")

    captured = capfd.readouterr()
    assert "local-event" in captured.out
