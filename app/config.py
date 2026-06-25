"""Runtime configuration: YAML/JSON file defaults, overridden by environment variables."""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

CONFIG_FILE_ENV = "HOC_CONFIG_FILE"
DEFAULT_CONFIG_PATHS = ["config.yaml", "config.yml", "config.json"]


class TemplateConstants(BaseModel):
    border_width_px: int = 4
    padding_px: int = 16
    line_spacing_px: int = 6
    header_font_size: int = 34
    product_font_size: int = 30
    attr_font_size: int = 22
    footer_font_size: int = 20


class Settings(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8080

    api_key: str = "change-me"

    allowed_cidrs: list[str] = Field(default_factory=lambda: ["127.0.0.1/32"])

    default_printer_model: str = "QL-700"
    default_label_width_mm: int = 62
    usb_backend: str = "pyusb"
    printer_identifier: str = ""

    preview_dir: str = "./data/previews"
    log_dir: str = "./data/logs"
    db_path: str = "./data/jobs.db"
    font_dir: str = "./fonts"

    debug: bool = False
    queue_concurrency: int = 1
    idempotency_window_seconds: int = 120
    rate_limit_per_minute: int = 60

    enabled_templates: list[str] = Field(default_factory=lambda: ["house-of-coffee-62mm"])
    template_constants: dict[str, TemplateConstants] = Field(default_factory=dict)

    def constants_for(self, template_name: str) -> TemplateConstants:
        return self.template_constants.get(template_name, TemplateConstants())


def _load_file_config() -> dict[str, Any]:
    path_str = os.environ.get(CONFIG_FILE_ENV)
    candidates = [path_str] if path_str else DEFAULT_CONFIG_PATHS
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        if path.is_file():
            text = path.read_text()
            if path.suffix in (".yaml", ".yml"):
                return yaml.safe_load(text) or {}
            if path.suffix == ".json":
                return json.loads(text)
    return {}


_ENV_PREFIX = "HOC_"


def _env_overrides(field_names: set[str]) -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    for key, value in os.environ.items():
        if not key.startswith(_ENV_PREFIX):
            continue
        field = key[len(_ENV_PREFIX):].lower()
        if field not in field_names:
            continue
        if field in ("allowed_cidrs", "enabled_templates"):
            overrides[field] = [v.strip() for v in value.split(",") if v.strip()]
        elif field in ("port", "default_label_width_mm", "queue_concurrency",
                       "idempotency_window_seconds", "rate_limit_per_minute"):
            overrides[field] = int(value)
        elif field == "debug":
            overrides[field] = value.strip().lower() in ("1", "true", "yes", "on")
        else:
            overrides[field] = value
    return overrides


@lru_cache
def get_settings() -> Settings:
    file_config = _load_file_config()
    base = Settings(**file_config) if file_config else Settings()
    env_overrides = _env_overrides(set(Settings.model_fields.keys()))
    if env_overrides:
        base = base.model_copy(update=env_overrides)
    return base
