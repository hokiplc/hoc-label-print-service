"""Process-wide singletons (job store, print queue) shared across API routes."""
from __future__ import annotations

from app.config import Settings, get_settings
from app.db import JobStore
from app.queue_worker import PrintQueue

_store: JobStore | None = None
_print_queue: PrintQueue | None = None


def get_store() -> JobStore:
    global _store
    if _store is None:
        settings = get_settings()
        _store = JobStore(settings.db_path)
    return _store


def get_print_queue() -> PrintQueue:
    global _print_queue
    if _print_queue is None:
        settings: Settings = get_settings()
        _print_queue = PrintQueue(settings, get_store())
    return _print_queue
