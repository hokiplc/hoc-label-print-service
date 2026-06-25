"""Rotating file + console logging. Never logs API keys or other secrets."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.config import Settings


def configure_logging(settings: Settings) -> None:
    log_dir = Path(settings.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    level = logging.DEBUG if settings.debug else logging.INFO
    fmt = "%(asctime)s %(levelname)s %(name)s %(message)s"

    root = logging.getLogger("hoc")
    root.setLevel(level)
    root.handlers.clear()

    file_handler = RotatingFileHandler(
        log_dir / "hoc-label-print.log", maxBytes=5 * 1024 * 1024, backupCount=5
    )
    file_handler.setFormatter(logging.Formatter(fmt))
    root.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(fmt))
    root.addHandler(console_handler)
