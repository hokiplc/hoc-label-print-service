"""Pydantic request/response schemas for the print job API."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

MAX_STRING_LEN = 80


class CoffeeLabelData(BaseModel):
    """Structured fields for the house-of-coffee-62mm template."""

    product_name: str = Field(..., min_length=1, max_length=MAX_STRING_LEN)
    grind: Optional[str] = Field(default="", max_length=MAX_STRING_LEN)
    weight: Optional[str] = Field(default="", max_length=MAX_STRING_LEN)
    strength: Optional[str] = Field(default="", max_length=10)
    flavour: Optional[str] = Field(default="", max_length=10)
    roast: Optional[str] = Field(default="", max_length=10)
    best_before: Optional[str] = Field(default="", max_length=MAX_STRING_LEN)

    @field_validator(
        "product_name", "grind", "weight", "strength", "flavour", "roast", "best_before",
        mode="before",
    )
    @classmethod
    def _normalize(cls, value: Any) -> Any:
        if value is None:
            return ""
        text = str(value).strip()
        return text[:MAX_STRING_LEN]


class PrintJobRequest(BaseModel):
    template: str = Field(..., min_length=1, max_length=64)
    printer: str = Field(default="ql-700", max_length=32)
    label_width_mm: int = Field(default=62, ge=12, le=103)
    copies: int = Field(default=1, ge=1, le=50)
    job_ref: Optional[str] = Field(default=None, max_length=128)
    data: CoffeeLabelData

    @field_validator("template")
    @classmethod
    def _strip_template(cls, value: str) -> str:
        return value.strip().lower()


class JobResponse(BaseModel):
    job_id: str
    status: str
    template: str
    job_ref: Optional[str] = None
    copies: int
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    preview_path: Optional[str] = None
    error_message: Optional[str] = None
    submitted_by_ip: Optional[str] = None

    class Config:
        from_attributes = True


class JobListResponse(BaseModel):
    jobs: list[JobResponse]


class HealthResponse(BaseModel):
    status: str
    version: str
    printer_model: str
    label_width_mm: int
    printer_identifier: str
    queue_depth: int
    queue_concurrency: int
    worker_alive: bool


class ConfigResponse(BaseModel):
    default_printer_model: str
    default_label_width_mm: int
    enabled_templates: list[str]
    queue_concurrency: int
    rate_limit_per_minute: int
    idempotency_window_seconds: int


class ErrorResponse(BaseModel):
    detail: str
    code: str = "error"
