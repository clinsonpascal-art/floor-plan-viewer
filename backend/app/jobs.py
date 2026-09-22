"""Small durable job registry and single-process execution queue.

SQLite persists job metadata across API restarts. Execution is intentionally
single-process; a Redis/Celery worker can replace the executor later without
changing the REST contract.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import httpx

from .config import settings
from .pipeline import generate_unit

_DB = Path(settings.job_db)
_DB.parent.mkdir(parents=True, exist_ok=True)
_LOCK = threading.Lock()
_EXECUTOR = ThreadPoolExecutor(max_workers=max(1, settings.job_workers))


def _now():
    return datetime.now(timezone.utc).isoformat()


def _conn():
    c = sqlite3.connect(_DB, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    with _conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY, project_id TEXT NOT NULL, unit_id TEXT NOT NULL, status TEXT NOT NULL,
            manifest_json TEXT, error TEXT, idempotency_key TEXT, webhook_url TEXT,
            plan_path TEXT, provider TEXT, staged INTEGER NOT NULL DEFAULT 0,
            only_json TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_project_idem
          ON jobs(project_id, idempotency_key) WHERE idempotency_key IS NOT NULL;
        """)
        # Lightweight migration for a DB created before these columns existed -
        # CREATE TABLE IF NOT EXISTS above won't add them to an already-existing
        # table.
        for ddl in (
            "ALTER TABLE jobs ADD COLUMN lighting_json TEXT",
            "ALTER TABLE jobs ADD COLUMN waterfront_type TEXT",
            "ALTER TABLE jobs ADD COLUMN city TEXT",
            "ALTER TABLE jobs ADD COLUMN direction TEXT",
            "ALTER TABLE jobs ADD COLUMN floor INTEGER",
            "ALTER TABLE jobs ADD COLUMN building_slug TEXT",
        ):
            try:
                c.execute(ddl)
            except sqlite3.OperationalError:
                pass
        c.execute("UPDATE jobs SET status='error', error='API restarted while job was running', updated_at=? WHERE status='running'", (_now(),))


def create_project(name: str = "LUXE Project") -> str:
    pid = uuid.uuid4().hex[:16]
    with _conn() as c:
        c.execute("INSERT INTO projects VALUES (?,?,?)", (pid, name, _now()))
    return pid


def project_exists(pid: str) -> bool:
    with _conn() as c:
        return c.execute("SELECT 1 FROM projects WHERE id=?", (pid,)).fetchone() is not None


def create(project_id: str, unit_id: str, plan: Path | None, staged: bool, only: list | None,
           provider: str | None, idempotency_key: str | None = None,
           webhook_url: str | None = None, lighting: list[str] | None = None,
           waterfront_type: str | None = None, city: str | None = None,
           direction: str | None = None, floor: int | None = None,
           building_slug: str | None = None) -> tuple[str, bool]:
    if idempotency_key:
        with _conn() as c:
            row = c.execute("SELECT id FROM jobs WHERE project_id=? AND idempotency_key=?", (project_id, idempotency_key)).fetchone()
            if row:
                return row["id"], True
    jid = uuid.uuid4().hex[:12]
    now = _now()
    with _conn() as c:
        c.execute("INSERT INTO jobs(id,project_id,unit_id,status,idempotency_key,webhook_url,plan_path,provider,staged,only_json,lighting_json,waterfront_type,city,direction,floor,building_slug,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (jid, project_id, unit_id, "pending", idempotency_key, webhook_url, str(plan) if plan else None,
                   provider, int(staged), json.dumps(only or []), json.dumps(lighting or []),
                   waterfront_type, city, direction, floor, building_slug, now, now))
    _EXECUTOR.submit(run, jid)
    return jid, False


def _update(jid: str, **fields):
    fields["updated_at"] = _now()
    keys = ",".join(f"{k}=?" for k in fields)
    with _conn() as c:
        c.execute(f"UPDATE jobs SET {keys} WHERE id=?", tuple(fields.values()) + (jid,))


def get(jid: str) -> dict | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM jobs WHERE id=?", (jid,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d.pop("only_json", None)
    d.pop("lighting_json", None)
    d.pop("plan_path", None)
    d["manifest"] = json.loads(d["manifest_json"]) if d.get("manifest_json") else None
    d.pop("manifest_json", None)
    return d


def run(jid: str):
    with _conn() as c:
        row = c.execute("SELECT * FROM jobs WHERE id=?", (jid,)).fetchone()
    if not row:
        return
    _update(jid, status="running", error=None)
    try:
        lighting = json.loads(row["lighting_json"] or "[]") or None
        manifest = generate_unit(row["unit_id"], Path(row["plan_path"]) if row["plan_path"] else None,
                                 bool(row["staged"]), json.loads(row["only_json"] or "[]") or None, row["provider"] or None,
                                 lighting, row["waterfront_type"], row["city"], row["direction"],
                                 row["floor"], row["building_slug"])
        _update(jid, status="done", manifest_json=json.dumps(manifest, ensure_ascii=False), error=None)
        _webhook(row["webhook_url"], jid, "done", manifest)
    except Exception as exc:
        _update(jid, status="error", error=str(exc))
        _webhook(row["webhook_url"], jid, "error", {"error": str(exc)})


def _webhook(url: str | None, jid: str, status: str, payload: dict):
    if not url:
        return
    try:
        httpx.post(url, json={"job_id": jid, "status": status, "result": payload}, timeout=10.0)
    except Exception:
        # A webhook failure must not change a completed generation into an error.
        pass


init_db()
