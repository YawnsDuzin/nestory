from __future__ import annotations

import logging
import sys

import structlog


def configure_logging(*, env: str = "local") -> None:
    level = logging.INFO

    renderer: structlog.types.Processor
    if env == "local":
        renderer = structlog.dev.ConsoleRenderer(colors=False)
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.WriteLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )
    logging.basicConfig(
        level=level,
        handlers=[logging.StreamHandler(sys.stdout)],
        format="%(message)s",
    )
