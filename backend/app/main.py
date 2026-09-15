"""LUXE deployable REST API.

Versioned API:
  POST /api/v1/projects
  POST /api/v1/projects/{id}/floor-plan
  POST /api/v1/projects/{id}/jobs
  GET  /api/v1/jobs/{id}
  GET  /api/v1/jobs/{id}/geometry
  GET  /api/v1/jobs/{id}/rooms
  GET  /api/v1/jobs/{id}/assets
  GET  /api/v1/jobs/{id}/viewer

Legacy /units and /jobs routes remain for compatibility with the earlier demo.
"""
from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.security import APIKeyHeader
from fastapi.staticfiles import StaticFiles

from . import jobs, tracking
from .config import settings

app = FastAPI(title="LUXE Floor Plan to 3D API", version="1.1.0", docs_url="/docs", redoc_url="/redoc")
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
                   allow_methods=["*"], allow_headers=["*"])

_OUT = Path(settings.out_dir)
_OUT.mkdir(parents=True, exist_ok=True)
app.mount(settings.public_base, StaticFiles(directory=str(_OUT)), name="renders")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def auth(key: str | None = Depends(api_key_header)):
    if settings.api_key and key != settings.api_key:
        raise HTTPException(401, "invalid or missing X-API-Key")
    return True


@app.get("/health")
def health():
    return {"ok": True, "provider": settings.provider, "model": settings.openai_model,
            "api_version": "v1", "authentication": bool(settings.api_key)}


@app.get("/api/v1/health")
def v1_health(_=Depends(auth)):
    return health()


@app.post("/api/v1/projects")
def create_project(name: str = Form("LUXE Project"), _=Depends(auth)):
    pid = jobs.create_project(name)
    return {"project_id": pid, "name": name, "status": "created"}


@app.post("/api/v1/projects/{project_id}/floor-plan")
async def upload_floor_plan(project_id: str, file: UploadFile = File(...), _=Depends(auth)):
    if not jobs.project_exists(project_id):
        raise HTTPException(404, "project not found")
    ext = Path(file.filename or "plan.jpg").suffix.lower() or ".jpg"
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise HTTPException(400, "floor plan must be JPG, PNG or WEBP")
    directory = _OUT / "_inputs" / project_id
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{uuid.uuid4().hex}{ext}"
    with path.open("wb") as dst:
        shutil.copyfileobj(file.file, dst)
    return {"project_id": project_id, "input_id": path.stem, "filename": file.filename,
            "path": str(path.relative_to(_OUT)), "status": "uploaded"}


def _resolve_plan(project_id: str, input_id: str | None) -> Path | None:
    if not input_id:
        return None
    d = _OUT / "_inputs" / project_id
    matches = list(d.glob(f"{input_id}.*"))
    if not matches:
        raise HTTPException(404, "input floor plan not found")
    return matches[0]


@app.post("/api/v1/projects/{project_id}/jobs")
async def create_job(project_id: str,
                     input_id: str | None = Form(None), unit_id: str | None = Form(None), staged: bool = Form(False),
                     only: str = Form(""), provider: str = Form(""),
                     webhook_url: str | None = Form(None),
                     file: UploadFile | None = File(None),
                     idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
                     _=Depends(auth)):
    if not jobs.project_exists(project_id):
        raise HTTPException(404, "project not found")
    plan = _resolve_plan(project_id, input_id)
    if file is not None:
        ext = Path(file.filename or "plan.jpg").suffix.lower() or ".jpg"
        if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
            raise HTTPException(400, "floor plan must be JPG, PNG or WEBP")
        directory = _OUT / "_inputs" / project_id
        directory.mkdir(parents=True, exist_ok=True)
        plan = directory / f"{uuid.uuid4().hex}{ext}"
        with plan.open("wb") as dst:
            shutil.copyfileobj(file.file, dst)
    if plan is None and project_id not in {"residence-a", "continuum-residence-01"}:
        raise HTTPException(400, "an uploaded floor plan is required for a new project")
    only_list = [s.strip() for s in only.split(",") if s.strip()] or None
    target_unit = unit_id or project_id
    jid, reused = jobs.create(project_id, target_unit, plan, staged, only_list, provider or None, idempotency_key, webhook_url)
    return {"job_id": jid, "project_id": project_id, "status": "pending", "idempotent_reuse": reused,
            "status_url": f"/api/v1/jobs/{jid}"}


@app.get("/api/v1/jobs/{job_id}")
def v1_job(job_id: str, _=Depends(auth)):
    j = jobs.get(job_id)
    if not j:
        raise HTTPException(404, "job not found")
    return j


@app.get("/api/v1/jobs/{job_id}/manifest")
def v1_manifest(job_id: str, _=Depends(auth)):
    j = jobs.get(job_id)
    if not j:
        raise HTTPException(404, "job not found")
    if j["status"] != "done" or not j.get("manifest"):
        raise HTTPException(409, "job is not complete")
    return j["manifest"]


@app.get("/api/v1/jobs/{job_id}/geometry")
def v1_geometry(job_id: str, _=Depends(auth)):
    m = _done_manifest(job_id)
    return {"job_id": job_id, "unit": m["unit"], "rooms": {rid: r["geometry"] for rid, r in m["rooms"].items()}}


@app.get("/api/v1/jobs/{job_id}/rooms")
def v1_rooms(job_id: str, _=Depends(auth)):
    m = _done_manifest(job_id)
    return {"job_id": job_id, "order": m["order"], "rooms": m["rooms"]}


@app.get("/api/v1/jobs/{job_id}/assets")
def v1_assets(job_id: str, _=Depends(auth)):
    m = _done_manifest(job_id)
    return {"job_id": job_id, "assets": [
        {"room_id": rid, "type": "room_render", "url": r.get("panorama_url")} for rid, r in m["rooms"].items()
    ]}


@app.get("/api/v1/jobs/{job_id}/viewer")
def v1_viewer(job_id: str, _=Depends(auth)):
    m = _done_manifest(job_id)
    return {"job_id": job_id, "viewer_url": f"{settings.viewer_base}/{m['unit']}?job_id={job_id}",
            "unit": m["unit"], "room_order": m["order"]}


def _unit_disk_manifest(unit_id: str) -> dict | None:
    p = _OUT / unit_id / "manifest.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def _resolve_viewer_manifest(unit_id: str, job_id: str | None) -> dict | None:
    """Pick the manifest that belongs to this job (preferred) or, absent a
    job_id, the most recently generated manifest on disk for this unit. This
    reuses the same job/manifest lookups as the /api/v1/jobs endpoints instead
    of re-parsing rooms.js/panoramas.js."""
    if job_id:
        j = jobs.get(job_id)
        if not j:
            raise HTTPException(404, "job not found")
        if j["unit_id"] != unit_id:
            raise HTTPException(404, "job does not belong to this unit")
        if j["status"] != "done" or not j.get("manifest"):
            raise HTTPException(409, "job is not complete")
        return j["manifest"]
    return _unit_disk_manifest(unit_id)


@app.get("/viewer/{unit_id}")
def viewer(unit_id: str, job_id: str | None = None):
    # The bundled viewer is a static shell; when a generated manifest is
    # available for this unit/job it is injected as window.LUXE_ROOMS /
    # LUXE_ORDER / LUXE_PANOS before the engine script runs, so the tour
    # renders that job's actual rooms instead of the built-in demo data.
    viewer_file = Path(__file__).resolve().parents[2] / "dist" / "luxe_virtual_tour.html"
    if not viewer_file.exists():
        raise HTTPException(404, "viewer bundle not found")
    html = viewer_file.read_text(encoding="utf-8")

    manifest = _resolve_viewer_manifest(unit_id, job_id)
    if manifest:
        rooms = manifest.get("rooms", {})
        order = manifest.get("order", [])
        panos = {rid: r["panorama_url"] for rid, r in rooms.items() if r.get("panorama_url")}

        def _safe_json(value) -> str:
            # Room names/features can originate from vision-parsed plan text;
            # neutralize "</script>" so that can never break out of the tag.
            return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")

        data_script = (
            "<script>"
            f"window.LUXE_ROOMS = {_safe_json(rooms)};"
            f"window.LUXE_ORDER = {_safe_json(order)};"
            f"window.LUXE_PANOS = {_safe_json(panos)};"
            "</script>"
        )
        label = f"UNIT {unit_id.upper()}" + (f" · JOB {job_id}" if job_id else "")
        html = html.replace(
            "<title>LUXE Virtual Tour — 1428 Brickell · Residence A</title>",
            f"<title>LUXE Virtual Tour — {unit_id}</title>", 1)
        html = html.replace(
            '<span class="unit">1428 BRICKELL · RESIDENCE A · 2BR / 3BA · 11′ CEILINGS · EAST / BISCAYNE BAY</span>',
            f'<span class="unit">{label}</span>', 1)
        html = html.replace("<script>", data_script + "<script>", 1)

    return HTMLResponse(content=html)


def _done_manifest(job_id: str) -> dict:
    j = jobs.get(job_id)
    if not j:
        raise HTTPException(404, "job not found")
    if j["status"] != "done" or not j.get("manifest"):
        raise HTTPException(409, "job is not complete")
    return j["manifest"]


# Backward-compatible demo routes.
@app.post("/units/{unit_id}/generate")
async def generate_legacy(unit_id: str, background: BackgroundTasks,
                          staged: bool = Form(False), only: str = Form(""),
                          provider: str = Form(""), file: UploadFile | None = File(None)):
    plan_path = None
    if file is not None:
        tmp = _OUT / "_legacy_inputs"
        tmp.mkdir(parents=True, exist_ok=True)
        plan_path = tmp / f"{uuid.uuid4().hex}{Path(file.filename or 'plan.jpg').suffix.lower()}"
        with plan_path.open("wb") as f:
            shutil.copyfileobj(file.file, f)
    # Legacy route uses a project record so it also benefits from durable jobs.
    if not jobs.project_exists(unit_id):
        # Known units are also valid project IDs for backwards compatibility.
        with jobs._conn() as c:
            c.execute("INSERT OR IGNORE INTO projects VALUES (?,?,?)", (unit_id, unit_id, jobs._now()))
    only_list = [s.strip() for s in only.split(",") if s.strip()] or None
    jid, _ = jobs.create(unit_id, unit_id, plan_path, staged, only_list, provider or None)
    tracking.track("unit3d_generate", {"unit": unit_id, "job": jid, "staged": staged})
    return {"job_id": jid}


@app.get("/jobs/{job_id}")
def legacy_job(job_id: str):
    j = jobs.get(job_id)
    if not j:
        raise HTTPException(404, "job not found")
    return j


@app.get("/units/{unit_id}/manifest")
def legacy_manifest(unit_id: str):
    p = _OUT / unit_id / "manifest.json"
    if not p.exists():
        raise HTTPException(404, "not generated yet")
    return json.loads(p.read_text(encoding="utf-8"))


@app.get("/units/{unit_id}/validate")
def legacy_validate(unit_id: str):
    p = _OUT / unit_id / "validation.json"
    if not p.exists():
        raise HTTPException(404, "not generated yet")
    return json.loads(p.read_text(encoding="utf-8"))


@app.post("/track")
def track(event: str = Form(...), data: str = Form("{}")):
    try:
        payload = json.loads(data)
    except Exception:
        payload = {}
    return {"accepted": tracking.track(event, payload)}
