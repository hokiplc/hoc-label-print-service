from __future__ import annotations

import io
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.auth import enforce_lan_and_key
from app.config import get_settings
from app.db import STATUS_CANCELLED, STATUS_COMPLETED, STATUS_FAILED
from app.schemas import JobListResponse, JobResponse, PrintJobRequest
from app.state import get_print_queue, get_store
from app.templates.registry import TemplateDisabledError, UnknownTemplateError, get_template

logger = logging.getLogger("hoc.api.jobs")

router = APIRouter(dependencies=[Depends(enforce_lan_and_key)])


def _to_response(job: dict) -> JobResponse:
    return JobResponse(
        job_id=job["job_id"],
        status=job["status"],
        template=job["template"],
        job_ref=job["job_ref"],
        copies=job["copies"],
        created_at=job["created_at"],
        started_at=job["started_at"],
        completed_at=job["completed_at"],
        preview_path=job["preview_path"],
        error_message=job["error_message"],
        submitted_by_ip=job["submitted_by_ip"],
    )


@router.post("/print-jobs", response_model=JobResponse, status_code=202)
def create_print_job(payload: PrintJobRequest, client_ip: str = Depends(enforce_lan_and_key)) -> JobResponse:
    settings = get_settings()
    store = get_store()

    if payload.template not in settings.enabled_templates:
        raise HTTPException(status_code=400, detail=f"Template not enabled: {payload.template}")

    if payload.job_ref:
        existing = store.find_recent_by_job_ref(payload.job_ref, settings.idempotency_window_seconds)
        if existing:
            logger.info("Idempotent replay for job_ref=%s -> job_id=%s", payload.job_ref, existing["job_id"])
            return _to_response(existing)

    job_id = store.create_job(
        template=payload.template,
        payload=payload.model_dump(),
        copies=payload.copies,
        job_ref=payload.job_ref,
        submitted_by_ip=client_ip,
    )
    get_print_queue().enqueue(job_id)
    logger.info("Queued job %s (job_ref=%s, template=%s)", job_id, payload.job_ref, payload.template)
    return _to_response(store.get_job(job_id))


@router.post("/print-jobs/preview")
def preview_print_job(payload: PrintJobRequest) -> FileResponse:
    settings = get_settings()
    try:
        template = get_template(payload.template, settings)
    except (UnknownTemplateError, TemplateDisabledError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    image = template.render(payload.data.model_dump(), payload.label_width_mm)

    preview_dir = Path(settings.preview_dir)
    preview_dir.mkdir(parents=True, exist_ok=True)
    filename = f"preview-{uuid.uuid4().hex}.png"
    path = preview_dir / filename
    image.save(path, format="PNG")

    return FileResponse(path, media_type="image/png", filename=filename)


@router.get("/print-jobs/{job_id}", response_model=JobResponse)
def get_print_job(job_id: str) -> JobResponse:
    store = get_store()
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return _to_response(job)


@router.get("/jobs", response_model=JobListResponse)
def list_jobs(limit: int = 50) -> JobListResponse:
    store = get_store()
    limit = max(1, min(limit, 200))
    jobs = [_to_response(j) for j in store.list_recent(limit)]
    return JobListResponse(jobs=jobs)


@router.post("/jobs/{job_id}/reprint", response_model=JobResponse, status_code=202)
def reprint_job(job_id: str) -> JobResponse:
    store = get_store()
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] not in (STATUS_COMPLETED, STATUS_FAILED, STATUS_CANCELLED):
        raise HTTPException(status_code=409, detail=f"Job is currently {job['status']}; cannot reprint yet")

    store.requeue(job_id)
    get_print_queue().enqueue(job_id)
    logger.info("Requeued job %s for reprint", job_id)
    return _to_response(store.get_job(job_id))
