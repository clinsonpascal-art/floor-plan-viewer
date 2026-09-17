"""End-to-end test of the REAL, deployed API surface for Alex's core ask:
"deliver an api that creates photorealistic photos from any floor plan which
is selected by a viewer" - a project id that is NOT Residence A or the
Continuum unit, with an uploaded floor-plan image, must go through the
deterministic detection pipeline (plan_detect.py / plan_parser.py) rather
than a hardcoded template, and must never fabricate a dimension it could not
actually measure.

Uses the mock render provider (no OPENAI_API_KEY required) so this exercises
the full HTTP flow - project create -> floor-plan upload -> job -> poll ->
manifest/geometry/rooms/assets/viewer - the same flow a real viewer/portal
would drive for a brand-new, previously-unseen floor plan.
"""
import os
import time
from pathlib import Path

os.environ.setdefault("LUXE_PROVIDER", "mock")

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app.config import settings  # noqa: E402

client = TestClient(app)

ROOT_PLAN = Path(__file__).resolve().parents[1] / "source_continuum_residence_01.jpg"

# Other test modules (test_api_v1.py/test_viewer.py) set LUXE_API_KEY before
# importing app.config, and Settings() is a process-wide singleton - whichever
# test module the collector imports first decides settings.api_key for the
# whole pytest session. Match test_viewer_clickable.py's own pattern rather
# than assume no auth is required.
_AUTH_HEADERS = {"X-API-Key": settings.api_key} if settings.api_key else {}


def _poll(job_id: str, timeout_s: float = 60.0):
    deadline = time.time() + timeout_s
    last = None
    while time.time() < deadline:
        last = client.get(f"/api/v1/jobs/{job_id}", headers=_AUTH_HEADERS).json()
        if last["status"] in ("done", "error"):
            return last
        time.sleep(0.3)
    return last


def test_arbitrary_new_floor_plan_end_to_end_via_real_api():
    # 1. A brand-new project - not "residence-a", not "continuum-residence-01".
    #    This is the "variable floor plan input" case: no authored template.
    r = client.post("/api/v1/projects", data={"name": "Client Portal Upload"}, headers=_AUTH_HEADERS)
    assert r.status_code == 200
    project_id = r.json()["project_id"]
    assert project_id not in ("residence-a", "continuum-residence-01")

    # 2. Viewer uploads an actual floor-plan image (the real, ornate Continuum
    #    source image is reused here purely as a real-world-complexity test
    #    image - it is intentionally NOT registered as this project's unit,
    #    so the server has no template for it and must analyze it fresh).
    with open(ROOT_PLAN, "rb") as f:
        r = client.post(f"/api/v1/projects/{project_id}/floor-plan",
                        files={"file": ("client_upload.jpg", f, "image/jpeg")}, headers=_AUTH_HEADERS)
    assert r.status_code == 200
    input_id = r.json()["input_id"]

    # 3. Kick off generation, limited to the first two detected regions so the
    #    test stays fast - detection itself still runs over the WHOLE image.
    r = client.post(f"/api/v1/projects/{project_id}/jobs", data={
        "input_id": input_id, "only": "room_1,room_2", "provider": "mock",
    }, headers=_AUTH_HEADERS)
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    job = _poll(job_id)
    assert job is not None and job["status"] == "done", (job or {}).get("error")

    # 4. Manifest/geometry/rooms/assets/viewer must all resolve for this job
    #    exactly like the existing known-unit flow.
    manifest = client.get(f"/api/v1/jobs/{job_id}/manifest", headers=_AUTH_HEADERS).json()
    assert manifest["unit"] == project_id
    assert set(manifest["order"]) == {"room_1", "room_2"}

    geometry = client.get(f"/api/v1/jobs/{job_id}/geometry", headers=_AUTH_HEADERS).json()
    rooms = client.get(f"/api/v1/jobs/{job_id}/rooms", headers=_AUTH_HEADERS).json()
    assets = client.get(f"/api/v1/jobs/{job_id}/assets", headers=_AUTH_HEADERS).json()
    viewer = client.get(f"/api/v1/jobs/{job_id}/viewer", headers=_AUTH_HEADERS).json()
    assert viewer["unit"] == project_id
    assert len(assets["assets"]) == 2

    for rid in ("room_1", "room_2"):
        room = manifest["rooms"][rid]
        # Real, detected polygon - not a hardcoded Residence A layout.
        assert room["geometry"]["source_polygon_px"]
        geom = geometry["rooms"][rid]
        # No printed dimension / scale reference exists for this upload -
        # the pipeline must say so honestly rather than invent a size.
        assert geom["width_ft"] is None and geom["depth_ft"] is None
        assert geom["source_fidelity"] == "dimensions_not_available_no_geometry_generated"
        assert room["dimension_source"] == "not_available"
        assert rooms["rooms"][rid]["panorama_url"]
