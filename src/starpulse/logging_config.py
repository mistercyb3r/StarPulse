"""Central logging setup for StarPulse.

Configures the ``starpulse`` logger tree with a console handler and an
optional rotating file handler, based on the loaded settings.
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

MAX_LOG_BYTES = 5 * 1024 * 1024  # 5 MB
BACKUP_COUNT = 3


def configure_logging(level: str = "INFO", log_file: str | Path | None = None) -> None:
    """Configure the root ``starpulse`` logger.

    Safe to call multiple times (e.g. in tests): existing handlers on the
    ``starpulse`` logger are replaced rather than duplicated.
    """
    logger = logging.getLogger("starpulse")
    logger.setLevel(level.upper())
    logger.propagate = False

    for handler in list(logger.handlers):
        logger.removeHandler(handler)

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    if log_file:
        file_path = Path(log_file)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            file_path, maxBytes=MAX_LOG_BYTES, backupCount=BACKUP_COUNT
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """Return a logger namespaced under ``starpulse``."""
    if name == "starpulse" or name.startswith("starpulse."):
        return logging.getLogger(name)
    return logging.getLogger(f"starpulse.{name}")
