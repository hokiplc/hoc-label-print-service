"""Smoke tests covering validation, auth, and template rendering without a physical
printer attached (the printer call itself is exercised only on real hardware)."""
from __future__ import annotations

import os

os.environ["HOC_API_KEY"] = "test-key"
os.environ["HOC_ALLOWED_CIDRS"] = ""
os.environ["HOC_DB_PATH"] = "./data/test-jobs.db"
os.environ["HOC_PREVIEW_DIR"] = "./data/test-previews"
os.environ["HOC_LOG_DIR"] = "./data/test-logs"

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app

get_settings.cache_clear()

client = TestClient(app)
HEADERS = {"X-API-Key": "test-key"}


def test_health_no_auth_required():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_jobs_requires_api_key():
    res = client.get("/jobs")
    assert res.status_code == 401


def test_jobs_rejects_wrong_key():
    res = client.get("/jobs", headers={"X-API-Key": "wrong"})
    assert res.status_code == 401


def test_create_print_job_unknown_template_rejected():
    payload = {
        "template": "not-a-real-template",
        "data": {"product_name": "Test Coffee"},
    }
    res = client.post("/print-jobs", json=payload, headers=HEADERS)
    assert res.status_code == 400


def test_create_print_job_accepted_and_queryable():
    payload = {
        "template": "house-of-coffee-62mm",
        "job_ref": "test-ref-001",
        "data": {
            "product_name": "DARK MONSOON MALABAR",
            "grind": "AeroPress",
            "weight": "0.454 kg",
            "strength": "4",
            "flavour": "3",
            "roast": "3",
            "best_before": "04.08.2027",
        },
    }
    res = client.post("/print-jobs", json=payload, headers=HEADERS)
    assert res.status_code == 202
    job = res.json()
    assert job["status"] == "queued"

    res2 = client.get(f"/print-jobs/{job['job_id']}", headers=HEADERS)
    assert res2.status_code == 200


def test_preview_renders_image():
    payload = {
        "template": "house-of-coffee-62mm",
        "data": {"product_name": "Preview Coffee", "best_before": "01.01.2030"},
    }
    res = client.post("/print-jobs/preview", json=payload, headers=HEADERS)
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/png"


def test_missing_product_name_rejected():
    payload = {"template": "house-of-coffee-62mm", "data": {}}
    res = client.post("/print-jobs", json=payload, headers=HEADERS)
    assert res.status_code == 422
