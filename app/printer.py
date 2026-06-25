"""Brother QL print backend. Wraps brother_ql's raster conversion and USB send,
translating its errors into structured, API-safe exceptions."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from PIL import Image

logger = logging.getLogger("hoc.printer")


class PrinterError(Exception):
    """Base class for all printer-facing errors. Safe to surface via the API."""


class PrinterNotFoundError(PrinterError):
    pass


class MediaMismatchError(PrinterError):
    pass


class PrinterCommunicationError(PrinterError):
    pass


@dataclass
class PrinterConfig:
    model: str
    label_width_mm: int
    backend: str
    identifier: str


class BrotherQLPrinter:
    def __init__(self, config: PrinterConfig) -> None:
        self.config = config

    def _label_name(self) -> str:
        # brother_ql continuous-roll label identifiers are named "<width>" (e.g. "62").
        return str(self.config.label_width_mm)

    def print_image(self, image: Image.Image, copies: int = 1) -> str:
        try:
            from brother_ql.backends.helpers import send
            from brother_ql.conversion import convert
            from brother_ql.raster import BrotherQLRaster
        except ImportError as exc:  # pragma: no cover - exercised only without the dep
            raise PrinterCommunicationError(f"brother_ql library not available: {exc}") from exc

        identifier = self.config.identifier or None

        try:
            qlr = BrotherQLRaster(self.config.model)
            qlr.exception_on_warning = True
            instructions = convert(
                qlr=qlr,
                images=[image] * copies,
                label=self._label_name(),
                rotate="0",
                threshold=70.0,
                dither=False,
                compress=False,
                red=False,
                dpi_600=False,
                hq=True,
                cut=True,
            )
        except Exception as exc:
            message = str(exc).lower()
            if "label" in message or "media" in message:
                raise MediaMismatchError(f"Label/media mismatch: {exc}") from exc
            raise PrinterCommunicationError(f"Failed to render print instructions: {exc}") from exc

        try:
            result = send(
                instructions=instructions,
                printer_identifier=identifier,
                backend_identifier=self.config.backend,
                blocking=True,
            )
        except Exception as exc:
            message = str(exc).lower()
            if "not found" in message or "no backend" in message or "no such device" in message:
                raise PrinterNotFoundError(f"Printer not found: {exc}") from exc
            raise PrinterCommunicationError(f"Printer communication error: {exc}") from exc

        if not result.get("did_print", False):
            status = result.get("status", "unknown")
            raise PrinterCommunicationError(f"Printer did not confirm print: {status}")

        return str(result)


def detect_printer(backend: str) -> list[str]:
    """Used by diagnostics to list attached USB printers."""
    try:
        from brother_ql.backends.helpers import discover

        return list(discover(backend_identifier=backend))
    except Exception as exc:
        logger.warning("Printer discovery failed: %s", exc)
        return []
