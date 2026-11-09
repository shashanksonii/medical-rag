"""Logging setup.

Design notes:
* Only handlers created here are managed (tagged), so calling ``setup_logging``
  repeatedly never duplicates handlers and never removes foreign handlers
  (for example pytest's ``caplog`` handler).
* Medical data must never be logged. Log identifiers and metadata only, never
  report text, observation values or request bodies.
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from app.core.config import Settings

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_MANAGED_FLAG = "_medrag_managed"


def _mark(handler: logging.Handler) -> logging.Handler:
    setattr(handler, _MANAGED_FLAG, True)
    return handler


def setup_logging(settings: Settings) -> None:
    """Configure root logging from ``settings``. Safe to call more than once."""
    root = logging.getLogger()

    for handler in list(root.handlers):
        if getattr(handler, _MANAGED_FLAG, False):
            root.removeHandler(handler)
            handler.close()

    formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)

    console = _mark(logging.StreamHandler(sys.stderr))
    console.setFormatter(formatter)
    root.addHandler(console)

    if settings.log_file is not None:
        settings.log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = _mark(
            RotatingFileHandler(
                settings.log_file,
                maxBytes=5_000_000,
                backupCount=3,
                encoding="utf-8",
            )
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    root.setLevel(settings.log_level)

    # Per-request lines are emitted by our own middleware (with request IDs),
    # so silence uvicorn's duplicate access log.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
