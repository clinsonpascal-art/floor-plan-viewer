"""Phase 2 (LUXE demo) regression: for a REAL completed job (real generation
pipeline, mock image provider - no network/API key needed), every room the
viewer receives via window.LUXE_ROOMS/LUXE_PANOS must actually be clickable
and show a real room visual:
  - a non-zero minimap rect (so the plan click-target isn't a zero-size point)
  - every doorway link has a chevron + position (so hotspots render, not
    "undefined" text)
  - every room has a panorama_url, and that URL actually serves a real image
    through the app's own static mount (not just present in the JSON)

This is distinct from tests/test_viewer.py, which seeds synthetic manifest
rows to test job/viewer plumbing in isolation. This test instead drives the
real pipeline (analyze.get_rooms -> pipeline.generate_unit -> the actual
continuum_template.py / hardcoded Residence A data) for both known units,
so it fails if a future change ever regresses real, API-generated
clickability - not just the plumbing around a hand-seeded fixture.
"""
import json
import os
import re
import time

os.environ.setdefault("LUXE_PROVIDER", "mock")
os.environ.setdefault("LUXE_OUT_DIR", "./renders_test")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app.config import settings  # noqa: E402

client = TestClient(app)

# app.config.settings is a process-wide singleton read from env vars at first
# import; another test module (e.g. test_viewer.py) may have already set
# LUXE_API_KEY before this module loads, which would make unauthenticated
# calls to /api/v1/... 401. Read whatever is actually configured right now
# and send it, instead of assuming no key is required.
_AUTH_HEADERS = {"X-API-Key": settings.api_key} if settings.api_key else {}


def _run_job(unit_id: str) -> str:
    jid = client.post(f"/units/{unit_id}/generate", data={"staged": "false", "provider": "mock"}).json()["job_id"]
    for _ in range(120):
        j = client.get(f"/jobs/{jid}").json()
        if j["status"] in ("done", "error"):
            break
        time.sleep(0.25)
    assert j["status"] == "done", j.get("error")
    return jid


def _extract(html: str, name: str) -> dict:
    m = re.search(r"window\." + name + r" = (\{.*?\});", html, re.S)
    assert m, f"{name} was not injected into the viewer page"
    return json.loads(m.group(1))


@pytest.mark.parametrize("unit_id", ["residence-a", "continuum-residence-01"])
def test_real_generated_rooms_are_clickable_end_to_end(unit_id):
    jid = _run_job(unit_id)

    html = client.get(f"/viewer/{unit_id}", params={"job_id": jid}).text
    rooms = _extract(html, "LUXE_ROOMS")
    panos = _extract(html, "LUXE_PANOS")

    assert rooms, "no rooms were injected into the viewer"

    for rid, room in rooms.items():
        assert room.get("w", 0) > 0 and room.get("h", 0) > 0, (
            f"{rid}: zero-size minimap rect - this room's plan tile would be an unclickable point"
        )
        for link in room.get("links", []):
            assert link.get("chev"), f"{rid}: doorway link to {link.get('to')} has no chevron"
            assert link.get("px") is not None and link.get("py") is not None, (
                f"{rid}: doorway link to {link.get('to')} has no hotspot position"
            )
        assert panos.get(rid), f"{rid}: no panorama_url - clicking this room has no visual to show"

    # Every advertised panorama actually resolves to a real served image, not
    # just a URL string sitting in the JSON.
    for rid, url in panos.items():
        resp = client.get(url)
        assert resp.status_code == 200, f"{rid}: panorama_url {url} does not resolve"
        assert resp.headers["content-type"].startswith("image/"), f"{rid}: {url} did not serve an image"

    # /api/v1/jobs/{id}/assets must agree with what the viewer shows.
    assets = client.get(f"/api/v1/jobs/{jid}/assets", headers=_AUTH_HEADERS).json()["assets"]
    asset_rooms = {a["room_id"] for a in assets}
    assert asset_rooms == set(rooms), "assets endpoint room set must match the viewer's room set"
