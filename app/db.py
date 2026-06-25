"""SQLite-backed job store. A single writer connection guarded by a lock keeps this
safe under FastAPI's threaded request handling and the background worker thread."""
from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    submitted_by_ip TEXT,
    job_ref TEXT,
    template TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL,
    copies INTEGER NOT NULL,
    preview_path TEXT,
    error_message TEXT
);
CREATE INDEX IF NOT EXISTS idx_jobs_job_ref ON jobs(job_ref);
CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at);
"""

STATUS_QUEUED = "queued"
STATUS_RENDERING = "rendering"
STATUS_PRINTING = "printing"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobStore:
    def __init__(self, db_path: str) -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    @contextmanager
    def _cursor(self) -> Iterator[sqlite3.Cursor]:
        with self._lock:
            cur = self._conn.cursor()
            try:
                yield cur
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def create_job(
        self,
        template: str,
        payload: dict[str, Any],
        copies: int,
        job_ref: Optional[str],
        submitted_by_ip: Optional[str],
    ) -> str:
        job_id = str(uuid.uuid4())
        with self._cursor() as cur:
            cur.execute(
                """INSERT INTO jobs
                (job_id, created_at, submitted_by_ip, job_ref, template, payload_json,
                 status, copies)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (job_id, now_iso(), submitted_by_ip, job_ref, template,
                 json.dumps(payload), STATUS_QUEUED, copies),
            )
        return job_id

    def get_job(self, job_id: str) -> Optional[dict[str, Any]]:
        with self._cursor() as cur:
            cur.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def find_recent_by_job_ref(self, job_ref: str, within_seconds: int) -> Optional[dict[str, Any]]:
        if within_seconds <= 0 or not job_ref:
            return None
        with self._cursor() as cur:
            cur.execute(
                "SELECT * FROM jobs WHERE job_ref = ? ORDER BY created_at DESC LIMIT 1",
                (job_ref,),
            )
            row = cur.fetchone()
        if not row:
            return None
        job = dict(row)
        created = datetime.fromisoformat(job["created_at"])
        age = (datetime.now(timezone.utc) - created).total_seconds()
        if age <= within_seconds and job["status"] not in (STATUS_FAILED, STATUS_CANCELLED):
            return job
        return None

    def list_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._cursor() as cur:
            cur.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,))
            return [dict(row) for row in cur.fetchall()]

    def update_status(
        self,
        job_id: str,
        status: str,
        started_at: Optional[str] = None,
        completed_at: Optional[str] = None,
        preview_path: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        fields = ["status = ?"]
        values: list[Any] = [status]
        if started_at is not None:
            fields.append("started_at = ?")
            values.append(started_at)
        if completed_at is not None:
            fields.append("completed_at = ?")
            values.append(completed_at)
        if preview_path is not None:
            fields.append("preview_path = ?")
            values.append(preview_path)
        if error_message is not None:
            fields.append("error_message = ?")
            values.append(error_message)
        values.append(job_id)
        with self._cursor() as cur:
            cur.execute(f"UPDATE jobs SET {', '.join(fields)} WHERE job_id = ?", values)

    def requeue(self, job_id: str) -> None:
        with self._cursor() as cur:
            cur.execute(
                """UPDATE jobs SET status = ?, started_at = NULL, completed_at = NULL,
                   error_message = NULL WHERE job_id = ?""",
                (STATUS_QUEUED, job_id),
            )

    def close(self) -> None:
        with self._lock:
            self._conn.close()
