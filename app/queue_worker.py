"""In-process print queue. A small pool of worker threads pulls jobs off a
queue.Queue, renders them, and prints them, so concurrent API requests never
collide on the single USB printer."""
from __future__ import annotations

import logging
import queue
import threading
from typing import Optional

from app.config import Settings
from app.db import (
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_PRINTING,
    STATUS_RENDERING,
    JobStore,
    now_iso,
)
from app.printer import BrotherQLPrinter, PrinterConfig, PrinterError
from app.templates import get_template
from app.templates.registry import TemplateDisabledError, UnknownTemplateError

logger = logging.getLogger("hoc.queue")


class PrintQueue:
    def __init__(self, settings: Settings, store: JobStore) -> None:
        self.settings = settings
        self.store = store
        self._queue: "queue.Queue[str]" = queue.Queue()
        self._threads: list[threading.Thread] = []
        self._stop_event = threading.Event()
        self._printer = BrotherQLPrinter(
            PrinterConfig(
                model=settings.default_printer_model,
                label_width_mm=settings.default_label_width_mm,
                backend=settings.usb_backend,
                identifier=settings.printer_identifier,
            )
        )

    def start(self) -> None:
        for i in range(max(1, self.settings.queue_concurrency)):
            t = threading.Thread(target=self._worker_loop, name=f"hoc-worker-{i}", daemon=True)
            t.start()
            self._threads.append(t)

    def stop(self) -> None:
        self._stop_event.set()
        for _ in self._threads:
            self._queue.put("")  # wake workers so they observe the stop event
        for t in self._threads:
            t.join(timeout=5)

    def enqueue(self, job_id: str) -> None:
        self._queue.put(job_id)

    def depth(self) -> int:
        return self._queue.qsize()

    def worker_alive(self) -> bool:
        return any(t.is_alive() for t in self._threads)

    def _worker_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                job_id = self._queue.get(timeout=1)
            except queue.Empty:
                continue
            if not job_id:
                continue
            try:
                self._process(job_id)
            except Exception:  # noqa: BLE001 - never let a bad job kill the worker
                logger.exception("Unhandled error processing job %s", job_id)
            finally:
                self._queue.task_done()

    def _process(self, job_id: str) -> None:
        import json

        job = self.store.get_job(job_id)
        if job is None:
            logger.warning("Job %s vanished before processing", job_id)
            return

        payload = json.loads(job["payload_json"])
        self.store.update_status(job_id, STATUS_RENDERING, started_at=now_iso())

        try:
            template = get_template(payload["template"], self.settings)
            image = template.render(payload["data"], payload.get("label_width_mm", 62))
        except (UnknownTemplateError, TemplateDisabledError) as exc:
            self._fail(job_id, str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            self._fail(job_id, f"Render failed: {exc}")
            return

        self.store.update_status(job_id, STATUS_PRINTING)
        try:
            result = self._printer.print_image(image, copies=job["copies"])
        except PrinterError as exc:
            self._fail(job_id, str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            self._fail(job_id, f"Unexpected print error: {exc}")
            return

        self.store.update_status(
            job_id, STATUS_COMPLETED, completed_at=now_iso(), error_message=result[:500]
        )
        logger.info("Job %s completed", job_id)

    def _fail(self, job_id: str, message: str) -> None:
        logger.error("Job %s failed: %s", job_id, message)
        self.store.update_status(
            job_id, STATUS_FAILED, completed_at=now_iso(), error_message=message[:1000]
        )
