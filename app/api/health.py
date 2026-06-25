from __future__ import annotations

from fastapi import APIRouter, Depends

from app import __version__
from app.auth import enforce_lan_and_key
from app.config import get_settings
from app.schemas import ConfigResponse, HealthResponse
from app.state import get_print_queue
from app.templates.registry import list_templates

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    pq = get_print_queue()
    return HealthResponse(
        status="ok",
        version=__version__,
        printer_model=settings.default_printer_model,
        label_width_mm=settings.default_label_width_mm,
        printer_identifier=settings.printer_identifier or "autodetect",
        queue_depth=pq.depth(),
        queue_concurrency=settings.queue_concurrency,
        worker_alive=pq.worker_alive(),
    )


@router.get("/config", response_model=ConfigResponse, dependencies=[Depends(enforce_lan_and_key)])
def config() -> ConfigResponse:
    settings = get_settings()
    return ConfigResponse(
        default_printer_model=settings.default_printer_model,
        default_label_width_mm=settings.default_label_width_mm,
        enabled_templates=list_templates(settings),
        queue_concurrency=settings.queue_concurrency,
        rate_limit_per_minute=settings.rate_limit_per_minute,
        idempotency_window_seconds=settings.idempotency_window_seconds,
    )
