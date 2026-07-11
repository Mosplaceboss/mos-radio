"""Centralized application logging."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from app.core.paths import logs_dir


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configure rotating file logging and return the studio logger."""
    logger = logging.getLogger("moplace.studio")
    if logger.handlers:
        return logger

    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(numeric_level)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    log_file = logs_dir() / "studio.log"
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=1_048_576,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(numeric_level)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.WARNING)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.propagate = False
    logger.info("Logging initialized at %s", log_file)
    return logger
