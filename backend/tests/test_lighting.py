"""Regression + new-capability tests for the lighting/daylight viewpoint
controls (sunrise/daylight/sunset/evening/night).

Two layers:
  - prompts.build_prompt(): pure-function check that each lighting condition
    actually produces different prompt text, and that omitting lighting is
    byte-identical to before the feature existed.
  - pipeline.generate_unit(): the real per-room generation loop (mock
    provider - no OpenAI/network), checking the manifest's viewpoints[]
    shape for the no-lighting (unchanged), multi-lighting (new), unknown/
    duplicate-filtering, and static-photo-override cases.
"""
import os
import time
from pathlib import Path

os.environ.setdefault("LUXE_PROVIDER", "mock")

import app.config as cfg  # noqa: E402
from app import prompts  # noqa: E402
from app.pipeline import generate_unit  # noqa: E402
from app.config import settings  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "source_continuum_residence_01.jpg"
client = TestClient(app)
# app.config.settings is a process-wide singleton decided by whichever test
# module imports it first (see test_viewer_clickable.py's own note on this) -
# read whatever is actually configured rather than assuming a key/value.
_AUTH_HEADERS = {"X-API-Key": settings.api_key} if settings.api_key else {}


def test_build_prompt_without_lighting_is_unchanged_default():
    # No lighting argument at all (the pre-existing call shape every current
    # caller uses) must fall back to the default condition exactly, so a job
    # created before this feature existed still gets today's output.
    no_arg = prompts.build_prompt("great", "Great Room", 18, 15, view=True)
    explicit_default = prompts.build_prompt("great", "Great Room", 18, 15, view=True,
                                            lighting=prompts.DEFAULT_LIGHTING)
    assert no_arg == explicit_default


def test_build_prompt_varies_by_lighting_condition():
    prompts_by_condition = {
        cond: prompts.build_prompt("great", "Great Room", 18, 15, view=True, lighting=cond)
        for cond in prompts.LIGHTING
    }
    # Every condition must produce genuinely different text (the sky/mood
    # clauses differ), and each must actually mention its own sky/mood cues.
    assert len(set(prompts_by_condition.values())) == len(prompts.LIGHTING)
    for cond, text in prompts_by_condition.items():
        assert prompts.LIGHTING[cond]["sky"] in text
        assert prompts.LIGHTING[cond]["mood"] in text


def test_build_prompt_unknown_lighting_falls_back_to_default():
    unknown = prompts.build_prompt("great", "Great Room", 18, 15, view=True, lighting="midnight-blizzard")
    default = prompts.build_prompt("great", "Great Room", 18, 15, view=True, lighting=prompts.DEFAULT_LIGHTING)
    assert unknown == default


def test_interior_room_body_unaffected_by_lighting_sky_clause():
    # An interior (non-view) room never gets the view/sky clause at all -
    # only its lighting *mood* should vary.
    sunrise = prompts.build_prompt("kitchen", "Kitchen", 15, 13, view=False, lighting="sunrise")
    night = prompts.build_prompt("kitchen", "Kitchen", 15, 13, view=False, lighting="night")
    assert sunrise != night
    assert prompts.LIGHTING["sunrise"]["sky"] not in sunrise
    assert prompts.LIGHTING["night"]["sky"] not in night


def test_generate_unit_without_lighting_produces_single_default_viewpoint():
    out = ROOT / "renders_lighting_test_default"
    old = cfg.settings.out_dir
    cfg.settings.out_dir = str(out)
    try:
        manifest = generate_unit("continuum-residence-01", PLAN, provider="mock", only=["bed2"])
        room = manifest["rooms"]["bed2"]
        assert room["viewpoints"] == [{"id": "main", "label": "Main View", "url": room["panorama_url"]}]
    finally:
        cfg.settings.out_dir = old


def test_generate_unit_with_lighting_produces_one_real_viewpoint_per_condition():
    out = ROOT / "renders_lighting_test_multi"
    old = cfg.settings.out_dir
    cfg.settings.out_dir = str(out)
    try:
        manifest = generate_unit("continuum-residence-01", PLAN, provider="mock",
                                 only=["bed2"], lighting=["sunrise", "daylight", "sunset"])
        room = manifest["rooms"]["bed2"]
        vps = room["viewpoints"]
        assert [v["id"] for v in vps] == ["sunrise", "daylight", "sunset"]
        assert [v["label"] for v in vps] == ["Sunrise", "Daylight", "Sunset"]

        # Every viewpoint's asset must be a real file that was actually written.
        unit_dir = out / "continuum-residence-01"
        urls = {v["url"] for v in vps}
        assert len(urls) == 3, "each lighting condition must get its own distinct asset URL"
        for v in vps:
            assert (unit_dir / f"bed2.{v['id']}.jpg").exists()

        # panorama_url (backward-compat single-image field) mirrors the FIRST
        # requested condition, and that file is a real, independently-written copy.
        assert room["panorama_url"].endswith("/bed2.jpg")
        assert (unit_dir / "bed2.jpg").exists()
        assert (unit_dir / "bed2.jpg").read_bytes() == (unit_dir / "bed2.sunrise.jpg").read_bytes()
    finally:
        cfg.settings.out_dir = old


def test_generate_unit_lighting_dedupes_and_drops_unknown_conditions():
    out = ROOT / "renders_lighting_test_filter"
    old = cfg.settings.out_dir
    cfg.settings.out_dir = str(out)
    try:
        manifest = generate_unit("continuum-residence-01", PLAN, provider="mock", only=["bed2"],
                                 lighting=["sunrise", "not-a-real-condition", "sunrise", "daylight"])
        vps = manifest["rooms"]["bed2"]["viewpoints"]
        assert [v["id"] for v in vps] == ["sunrise", "daylight"], (
            "unknown conditions must be dropped and duplicates collapsed, order preserved"
        )
    finally:
        cfg.settings.out_dir = old


def test_api_job_creation_accepts_lighting_field_end_to_end():
    project = client.post("/api/v1/projects", headers=_AUTH_HEADERS, data={"name": "Lighting API test"})
    assert project.status_code == 200
    pid = project.json()["project_id"]
    with PLAN.open("rb") as f:
        upload = client.post(f"/api/v1/projects/{pid}/floor-plan", headers=_AUTH_HEADERS,
                             files={"file": (PLAN.name, f, "image/jpeg")})
    assert upload.status_code == 200
    input_id = upload.json()["input_id"]

    r = client.post(f"/api/v1/projects/{pid}/jobs", headers=_AUTH_HEADERS, data={
        "input_id": input_id, "unit_id": "continuum-residence-01",
        "only": "bed2", "provider": "mock", "lighting": "sunrise,daylight",
    })
    assert r.status_code == 200
    jid = r.json()["job_id"]

    status = None
    for _ in range(300):
        status = client.get(f"/api/v1/jobs/{jid}", headers=_AUTH_HEADERS).json()
        if status["status"] in {"done", "error"}:
            break
        time.sleep(0.1)
    assert status["status"] == "done", status

    rooms = client.get(f"/api/v1/jobs/{jid}/rooms", headers=_AUTH_HEADERS).json()["rooms"]
    vps = rooms["bed2"]["viewpoints"]
    assert [v["id"] for v in vps] == ["sunrise", "daylight"]
    assert [v["label"] for v in vps] == ["Sunrise", "Daylight"]


def test_generate_unit_static_photo_override_without_lighting_is_unchanged():
    # "great" has a real curated static photo for continuum-residence-01
    # (see static_room_images.py). With no lighting requested, behavior is
    # exactly what it was before the lighting feature existed.
    out = ROOT / "renders_lighting_test_static_nolighting"
    old = cfg.settings.out_dir
    cfg.settings.out_dir = str(out)
    try:
        manifest = generate_unit("continuum-residence-01", PLAN, provider="mock", only=["great"])
        vps = manifest["rooms"]["great"]["viewpoints"]
        assert vps == [{"id": "main", "label": "Main View", "url": manifest["rooms"]["great"]["panorama_url"]}]
    finally:
        cfg.settings.out_dir = old


def test_generate_unit_static_photo_override_with_lighting_reuses_curated_as_daylight():
    # A curated room must NOT be excluded from lighting: the existing real
    # photo becomes the "daylight" viewpoint (reused byte-for-byte, never
    # regenerated or deleted), and every other requested condition is
    # generated fresh - same as any other room.
    import hashlib
    STATIC_DIR = ROOT / "static"
    from app.static_room_images import STATIC_ROOM_IMAGES
    curated_path = STATIC_DIR / STATIC_ROOM_IMAGES["continuum-residence-01"]["great"]

    out = ROOT / "renders_lighting_test_static_withlighting"
    old = cfg.settings.out_dir
    cfg.settings.out_dir = str(out)
    try:
        manifest = generate_unit("continuum-residence-01", PLAN, provider="mock", only=["great"],
                                 lighting=["sunrise", "sunset"])
        vps = manifest["rooms"]["great"]["viewpoints"]
        # "daylight" is always included (the reused curated photo), forced
        # first, even though it wasn't in the requested list.
        assert [v["id"] for v in vps] == ["daylight", "sunrise", "sunset"]

        unit_dir = out / "continuum-residence-01"
        daylight_file = unit_dir / "great.daylight.jpg"
        assert daylight_file.exists()
        assert hashlib.sha256(daylight_file.read_bytes()).hexdigest() == hashlib.sha256(curated_path.read_bytes()).hexdigest(), (
            "the daylight viewpoint must be the real curated photo, byte-for-byte, not regenerated"
        )
        # The other conditions are real, distinct, freshly generated files.
        assert (unit_dir / "great.sunrise.jpg").exists()
        assert (unit_dir / "great.sunset.jpg").exists()
        # panorama_url (backward-compat) mirrors daylight, i.e. the curated photo.
        assert manifest["rooms"]["great"]["panorama_url"].endswith("/great.jpg")
        assert hashlib.sha256((unit_dir / "great.jpg").read_bytes()).hexdigest() == hashlib.sha256(curated_path.read_bytes()).hexdigest()
    finally:
        cfg.settings.out_dir = old
