"""Centralized structured logging setup."""

import logging
from pathlib import Path

import structlog

from config import LOG_DIR


def configure_logging(level: str = "INFO") -> structlog.BoundLogger:
    log_path: Path = LOG_DIR / "pipeline.log"
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(message)s",
        handlers=[
            logging.FileHandler(log_path),
            logging.StreamHandler(),
        ],
    )
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
    )
    return structlog.get_logger()


log = configure_logging()
