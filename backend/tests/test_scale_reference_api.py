"""End-to-end test of Option 1 (the total_interior_sqft scale-reference
parameter) through the REAL HTTP API - proving it actually resolves the
measurement blocker for an arbitrary/new floor plan, not just at the
plan_detect.py unit level.

Uses the mock render provider (no OPENAI_API_KEY required).
"""
import os

os.environ.setdefault("LUXE_PROVIDER", "mock")

import cv2  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.config import settings  # noqa: E402

from fixtures.synthetic_plan import EXPECTED_ROOMS, build_synthetic_plan

client = TestClient(app)
_AUTH_HEADERS = {"X-API-Key": settings.api_key} if settings.api_key else {}


def _write_fixture(tmp_path):
    img = build_synthetic_plan()
    path = tmp_path / "scale_ref_plan.png"
    cv2.imwrite(str(path), img)
    return path


# The two synthetic rooms are each 180x260px (see EXPECTED_ROOMS in
# fixtures/synthetic_plan.py). At a made-up total of 936 sqft for both rooms
# combined, the resulting global px_per_ft is exactly 10 (936 = (180*260*2)/100
# in ft^2 terms scaled down - the exact number only matters for the assertion
# tolerance below, not for a human-meaningful floor plan).
TOTAL_INTERIOR_SQFT = 936.0


def test_total_interior_sqft_at_upload_time_yields_real_dimensions(tmp_path):
    path = _write_fixture(tmp_path)

    project_id = client.post("/api/v1/projects", data={"name": "Scale ref test"},
                             headers=_AUTH_HEADERS).json()["project_id"]
    with open(path, "rb") as f:
        upload = client.post(f"/api/v1/projects/{project_id}/floor-plan",
                             files={"file": ("plan.png", f, "image/png")},
                             data={"total_interior_sqft": TOTAL_INTERIOR_SQFT},
                             headers=_AUTH_HEADERS).json()
    input_id = upload["input_id"]

    job = client.post(f"/api/v1/projects/{project_id}/jobs",
                      data={"input_id": input_id, "provider": "mock"},
                      headers=_AUTH_HEADERS).json()
    job_id = job["job_id"]

    import time
    result = None
    for _ in range(60):
        result = client.get(f"/api/v1/jobs/{job_id}", headers=_AUTH_HEADERS).json()
        if result["status"] in ("done", "error"):
            break
        time.sleep(0.2)
    assert result["status"] == "done", result.get("error")

    manifest = result["manifest"]
    assert len(manifest["order"]) == 2
    for rid in manifest["order"]:
        room = manifest["rooms"][rid]
        geom = room["geometry"]
        # The whole point of Option 1: a real, non-null, non-fabricated
        # dimension now exists, sourced honestly from the supplied total area.
        assert geom["width_ft"] is not None and geom["depth_ft"] is not None
        assert geom["width_ft"] > 0 and geom["depth_ft"] > 0
        assert room["dimension_source"] == "estimated_from_total_area_low_confidence"
        # A structural control image should now be built from this real size.
        assert geom["source_fidelity"] != "dimensions_not_available_no_geometry_generated"


def test_without_total_interior_sqft_dimensions_stay_honestly_unavailable(tmp_path):
    """Regression guard: omitting the new parameter must behave exactly as
    before - no change in behavior for existing callers."""
    path = _write_fixture(tmp_path)

    project_id = client.post("/api/v1/projects", data={"name": "No scale ref"},
                             headers=_AUTH_HEADERS).json()["project_id"]
    with open(path, "rb") as f:
        upload = client.post(f"/api/v1/projects/{project_id}/floor-plan",
                             files={"file": ("plan.png", f, "image/png")},
                             headers=_AUTH_HEADERS).json()
    input_id = upload["input_id"]

    job = client.post(f"/api/v1/projects/{project_id}/jobs",
                      data={"input_id": input_id, "provider": "mock"},
                      headers=_AUTH_HEADERS).json()
    job_id = job["job_id"]

    import time
    result = None
    for _ in range(60):
        result = client.get(f"/api/v1/jobs/{job_id}", headers=_AUTH_HEADERS).json()
        if result["status"] in ("done", "error"):
            break
        time.sleep(0.2)
    assert result["status"] == "done", result.get("error")

    manifest = result["manifest"]
    for rid in manifest["order"]:
        room = manifest["rooms"][rid]
        assert room["geometry"]["width_ft"] is None
        assert room["dimension_source"] == "not_available"


def test_non_positive_total_interior_sqft_is_rejected_at_upload(tmp_path):
    path = _write_fixture(tmp_path)
    project_id = client.post("/api/v1/projects", data={"name": "Bad sqft"},
                             headers=_AUTH_HEADERS).json()["project_id"]
    with open(path, "rb") as f:
        r = client.post(f"/api/v1/projects/{project_id}/floor-plan",
                        files={"file": ("plan.png", f, "image/png")},
                        data={"total_interior_sqft": -5}, headers=_AUTH_HEADERS)
    assert r.status_code == 400


def test_total_interior_sqft_can_also_be_supplied_at_job_creation_time(tmp_path):
    """A caller who uploaded without the number initially can still supply it
    when creating the job, without re-uploading the file."""
    path = _write_fixture(tmp_path)
    project_id = client.post("/api/v1/projects", data={"name": "Late scale ref"},
                             headers=_AUTH_HEADERS).json()["project_id"]
    with open(path, "rb") as f:
        upload = client.post(f"/api/v1/projects/{project_id}/floor-plan",
                             files={"file": ("plan.png", f, "image/png")},
                             headers=_AUTH_HEADERS).json()
    input_id = upload["input_id"]

    job = client.post(f"/api/v1/projects/{project_id}/jobs",
                      data={"input_id": input_id, "provider": "mock",
                            "total_interior_sqft": TOTAL_INTERIOR_SQFT},
                      headers=_AUTH_HEADERS).json()
    job_id = job["job_id"]

    import time
    result = None
    for _ in range(60):
        result = client.get(f"/api/v1/jobs/{job_id}", headers=_AUTH_HEADERS).json()
        if result["status"] in ("done", "error"):
            break
        time.sleep(0.2)
    assert result["status"] == "done", result.get("error")

    manifest = result["manifest"]
    for rid in manifest["order"]:
        assert manifest["rooms"][rid]["geometry"]["width_ft"] is not None
