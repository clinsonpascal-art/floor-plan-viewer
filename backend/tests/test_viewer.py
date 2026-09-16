"""Proves /viewer/{unit_id} is data-driven: two different jobs/units render
different room data, instead of always showing the static Residence-A demo.

Job/manifest rows are seeded directly through app.jobs' own persistence layer
(the same SQLite table and row shape the real pipeline writes), so this
exercises the real job lookup and viewer-injection code without depending on
network access, a paid AI API, or actual image generation."""
import json
import os
import uuid

os.environ.setdefault("LUXE_PROVIDER", "mock")
os.environ.setdefault("LUXE_OUT_DIR", "./renders_api_test")
os.environ.setdefault("LUXE_JOB_DB", "./luxe_api_test.sqlite3")
os.environ.setdefault("LUXE_API_KEY", "test-key")

from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
from app import jobs as jobs_module
from pathlib import Path

client = TestClient(app)

ROOMS_A = {
    "foyer": {"name": "Seed Unit A Foyer", "dim": "20 x 6", "view": False, "feat": "Entry",
              "x": 96, "y": 20, "w": 34, "h": 22, "links": [],
              "panorama_url": "/renders/residence-a/foyer.jpg"},
    "great": {"name": "Seed Unit A Great Room", "dim": "18 x 15", "view": True, "feat": "Bay view",
              "x": 46, "y": 88, "w": 46, "h": 44, "links": [],
              "panorama_url": "/renders/residence-a/great.jpg"},
}
ORDER_A = ["foyer", "great"]

ROOMS_C = {
    "great": {"name": "Seed Unit C Living Room", "dim": "20 x 12", "view": True, "feat": "Living",
              "x": 0, "y": 0, "w": 0, "h": 0, "links": [],
              "panorama_url": "/renders/continuum-residence-01/great.jpg"},
    "powder": {"name": "Seed Unit C Powder Room", "dim": "Approximate terrace footprint from plan", "view": False, "feat": "Guest bath",
               "x": 0, "y": 0, "w": 0, "h": 0, "links": [],
               "panorama_url": "/renders/continuum-residence-01/powder.jpg"},
}
ORDER_C = ["great", "powder"]


def _seed_done_job(unit_id: str, rooms: dict, order: list) -> str:
    """Insert a completed job row the same way app.jobs.run() would, without
    invoking the (unrelated, platform-specific) image-generation pipeline."""
    project_id = jobs_module.create_project(f"seed-{unit_id}")
    jid = "seed" + uuid.uuid4().hex[:8]
    manifest = {"unit": unit_id, "status": "review_required", "order": order, "rooms": rooms}
    now = jobs_module._now()
    with jobs_module._conn() as c:
        c.execute(
            "INSERT INTO jobs(id,project_id,unit_id,status,manifest_json,idempotency_key,"
            "webhook_url,plan_path,provider,staged,only_json,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (jid, project_id, unit_id, "done", json.dumps(manifest), None, None, None,
             "mock", 0, "[]", now, now),
        )
    return jid


def test_viewer_renders_data_belonging_to_its_own_job():
    job_a = _seed_done_job("residence-a", ROOMS_A, ORDER_A)
    job_c = _seed_done_job("continuum-residence-01", ROOMS_C, ORDER_C)

    html_a = client.get(f"/viewer/residence-a?job_id={job_a}").text
    html_c = client.get(f"/viewer/continuum-residence-01?job_id={job_c}").text

    assert html_a != html_c

    # Room names unique to each seeded job must appear only in that job's own
    # viewer output — proving the viewer is not always the static demo.
    assert "Seed Unit A Foyer" in html_a
    assert "Seed Unit A Foyer" not in html_c

    assert "Seed Unit C Powder Room" in html_c
    assert "Seed Unit C Powder Room" not in html_a

    # Each viewer must reference its own job's own panorama assets.
    assert "/renders/residence-a/" in html_a
    assert "/renders/continuum-residence-01/" in html_c
    assert "/renders/residence-a/" not in html_c
    assert "/renders/continuum-residence-01/" not in html_a


def test_viewer_rejects_job_from_a_different_unit():
    job_a = _seed_done_job("residence-a", ROOMS_A, ORDER_A)
    resp = client.get(f"/viewer/continuum-residence-01?job_id={job_a}")
    assert resp.status_code == 404


def test_viewer_rejects_unfinished_job():
    project_id = jobs_module.create_project("seed-pending")
    jid = "pending" + uuid.uuid4().hex[:8]
    now = jobs_module._now()
    with jobs_module._conn() as c:
        c.execute(
            "INSERT INTO jobs(id,project_id,unit_id,status,idempotency_key,webhook_url,"
            "plan_path,provider,staged,only_json,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (jid, project_id, "residence-a", "running", None, None, None, "mock", 0, "[]", now, now),
        )
    resp = client.get(f"/viewer/residence-a?job_id={jid}")
    assert resp.status_code == 409


def test_viewer_without_job_id_falls_back_to_latest_unit_manifest():
    unit_dir = Path(settings.out_dir) / "residence-a"
    unit_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"unit": "residence-a", "status": "review_required", "order": ORDER_A, "rooms": ROOMS_A}
    (unit_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

    resp = client.get("/viewer/residence-a")
    assert resp.status_code == 200
    assert "Seed Unit A Foyer" in resp.text


def test_viewer_falls_back_to_static_demo_when_nothing_generated():
    resp = client.get("/viewer/never-generated-unit-xyz")
    assert resp.status_code == 200
    # No manifest exists for this unit, so the bundled static shell is served
    # unchanged (existing pre-fix behavior is preserved as a fallback).
    assert "LUXE Virtual Tour" in resp.text
