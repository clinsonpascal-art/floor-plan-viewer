"""Regression + new-capability tests for the dynamic outlook system
(waterfront_type / city / direction / floor elevation), kept separate from
the lighting/daylight feature (see test_lighting.py) per Requirement 11.

Three layers, mirroring test_lighting.py's structure:
  - prompts.get_view_clause()/build_prompt(): pure-function checks that
    omitting the new params reproduces today's fixed view text exactly, and
    that each new axis (waterfront_type, city, direction, floor, daylight)
    independently varies the generated text.
  - pipeline.generate_unit(): the real per-room generation loop (mock
    provider - no OpenAI/network) with the new params threaded through, and
    the building_slug manifest field.
  - main.py: the new fields end-to-end through both the v1 API and the
    legacy /units/{unit_id}/generate compatibility route.
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
_AUTH_HEADERS = {"X-API-Key": settings.api_key} if settings.api_key else {}


# --- prompts.get_view_clause() -------------------------------------------

def test_get_view_clause_without_new_params_matches_view_clause():
    # No waterfront_type/city/direction/floor at all -> byte-identical to
    # view_clause(), so every caller that only ever passed lighting/daylight
    # keeps getting exactly today's fixed Biscayne Bay text.
    for cond in prompts.LIGHTING:
        assert prompts.get_view_clause(daylight=cond) == prompts.view_clause(cond)
    assert prompts.get_view_clause() == prompts.view_clause(prompts.DEFAULT_LIGHTING)


def test_build_prompt_without_new_outlook_params_is_unchanged():
    # Same regression guarantee at the build_prompt() layer used by the
    # pipeline: adding the new kwargs to the signature must not change output
    # for a caller that never passes them.
    before = prompts.CAMERA  # sanity the module still imports cleanly
    assert before
    for cond in prompts.LIGHTING:
        with_lighting_only = prompts.build_prompt("great", "Great Room", 18, 15, view=True, lighting=cond)
        explicit_none = prompts.build_prompt("great", "Great Room", 18, 15, view=True, lighting=cond,
                                             waterfront_type=None, city=None, direction=None, floor=None)
        assert with_lighting_only == explicit_none
        assert prompts.view_clause(cond) in with_lighting_only


def test_get_view_clause_varies_by_waterfront_type():
    texts = {
        wf: prompts.get_view_clause(daylight="daylight", waterfront_type=wf, city="Miami")
        for wf in prompts.WATERFRONT_TYPES
    }
    assert len(set(texts.values())) == len(prompts.WATERFRONT_TYPES)
    for wf, text in texts.items():
        assert prompts.WATERFRONT_TYPES[wf] in text


def test_get_view_clause_unknown_waterfront_type_falls_back_to_default():
    unknown = prompts.get_view_clause(daylight="daylight", waterfront_type="lagoonfront", city="Miami")
    default = prompts.get_view_clause(daylight="daylight", waterfront_type=prompts.DEFAULT_WATERFRONT_TYPE,
                                      city="Miami")
    assert unknown == default


def test_get_view_clause_varies_by_city():
    miami = prompts.get_view_clause(daylight="daylight", waterfront_type="bayfront", city="Miami")
    fll = prompts.get_view_clause(daylight="daylight", waterfront_type="bayfront", city="Fort Lauderdale")
    assert miami != fll
    assert "Miami" in miami
    assert "Fort Lauderdale" in fll


def test_get_view_clause_varies_by_direction():
    east = prompts.get_view_clause(daylight="daylight", waterfront_type="oceanfront", direction="east")
    west = prompts.get_view_clause(daylight="daylight", waterfront_type="oceanfront", direction="west")
    none = prompts.get_view_clause(daylight="daylight", waterfront_type="oceanfront")
    assert east != west != none
    assert "facing east" in east
    assert "facing west" in west
    assert "facing" not in none


def test_get_view_clause_direction_normalizes_abbreviations_and_case():
    abbrev = prompts.get_view_clause(daylight="daylight", waterfront_type="oceanfront", direction="ne")
    full_upper = prompts.get_view_clause(daylight="daylight", waterfront_type="oceanfront", direction="Northeast")
    assert abbrev == full_upper
    assert "facing northeast" in abbrev


def test_get_view_clause_unrecognized_direction_is_still_used_verbatim():
    text = prompts.get_view_clause(daylight="daylight", waterfront_type="oceanfront", direction="poolside")
    assert "facing poolside" in text


def test_get_view_clause_floor_elevation_bands():
    low = prompts.get_view_clause(daylight="daylight", waterfront_type="oceanfront", floor=8)
    mid = prompts.get_view_clause(daylight="daylight", waterfront_type="oceanfront", floor=25)
    high = prompts.get_view_clause(daylight="daylight", waterfront_type="oceanfront", floor=52)
    assert len({low, mid, high}) == 3
    assert "tree canopy" in low
    assert "mid-level vista" in mid
    assert "high-altitude outlook" in high


def test_get_view_clause_floor_elevation_band_boundaries():
    band_text = {
        1: "tree canopy", 15: "tree canopy",
        16: "mid-level vista", 35: "mid-level vista",
        36: "high-altitude outlook", 70: "high-altitude outlook", 120: "high-altitude outlook",
    }
    for floor, fragment in band_text.items():
        text = prompts.get_view_clause(daylight="daylight", waterfront_type="oceanfront", floor=floor)
        assert fragment in text, f"floor {floor} should mention '{fragment}'"


def test_get_view_clause_floor_below_band_one_has_no_elevation_clause():
    for floor in (0, -5):
        text = prompts.get_view_clause(daylight="daylight", waterfront_type="oceanfront", floor=floor)
        assert "tree canopy" not in text
        assert "mid-level vista" not in text
        assert "high-altitude outlook" not in text


def test_get_view_clause_invalid_floor_value_is_ignored_not_an_error():
    text = prompts.get_view_clause(daylight="daylight", waterfront_type="oceanfront", floor="penthouse")
    assert "tree canopy" not in text
    assert "mid-level vista" not in text
    assert "high-altitude outlook" not in text


def test_get_view_clause_daylight_affects_atmosphere():
    texts = {
        cond: prompts.get_view_clause(daylight=cond, waterfront_type="oceanfront", city="Miami")
        for cond in prompts.LIGHTING
    }
    assert len(set(texts.values())) == len(prompts.LIGHTING)
    for cond, text in texts.items():
        assert prompts.LIGHTING[cond]["atmosphere"] in text


def test_get_view_clause_unknown_daylight_falls_back_to_default_in_dynamic_branch():
    unknown = prompts.get_view_clause(daylight="midnight-blizzard", waterfront_type="oceanfront")
    default = prompts.get_view_clause(daylight=prompts.DEFAULT_LIGHTING, waterfront_type="oceanfront")
    assert unknown == default


def test_get_view_clause_all_params_compose_together():
    text = prompts.get_view_clause(daylight="sunset", waterfront_type="intracoastal",
                                   city="Fort Lauderdale", direction="southwest", floor=44)
    assert prompts.WATERFRONT_TYPES["intracoastal"] in text
    assert "Fort Lauderdale" in text
    assert "facing southwest" in text
    assert "high-altitude outlook" in text
    assert prompts.LIGHTING["sunset"]["atmosphere"] in text


def test_get_view_clause_urban_skyline_has_no_water_wording():
    text = prompts.get_view_clause(daylight="daylight", waterfront_type="urban_skyline", city="Miami")
    assert "the city skyline" in text
    assert "bay" not in text.lower()
    assert "ocean" not in text.lower()


def test_interior_room_unaffected_by_outlook_params():
    # Interior (non-view) rooms must never receive the view/outlook clause,
    # regardless of what outlook params are passed.
    text = prompts.build_prompt("kitchen", "Kitchen", 15, 13, view=False, lighting="sunset",
                                waterfront_type="oceanfront", city="Miami", direction="east", floor=40)
    assert prompts.INTERIOR_CLAUSE in text
    assert prompts.WATERFRONT_TYPES["oceanfront"] not in text


def test_build_prompt_forwards_outlook_params_to_get_view_clause():
    expected_view = prompts.get_view_clause(daylight="sunrise", waterfront_type="bayfront",
                                            city="Miami", direction="north", floor=20)
    text = prompts.build_prompt("great", "Great Room", 18, 15, view=True, lighting="sunrise",
                                waterfront_type="bayfront", city="Miami", direction="north", floor=20)
    assert expected_view in text


# --- pipeline.generate_unit() ---------------------------------------------

def test_generate_unit_without_outlook_params_manifest_unchanged():
    out = ROOT / "renders_view_clause_test_default"
    old = cfg.settings.out_dir
    cfg.settings.out_dir = str(out)
    try:
        manifest = generate_unit("continuum-residence-01", PLAN, provider="mock", only=["bed2"])
        assert "building_slug" not in manifest
    finally:
        cfg.settings.out_dir = old


def test_generate_unit_with_outlook_params_succeeds_and_records_building_slug():
    out = ROOT / "renders_view_clause_test_full"
    old = cfg.settings.out_dir
    cfg.settings.out_dir = str(out)
    try:
        manifest = generate_unit("continuum-residence-01", PLAN, provider="mock", only=["bed2"],
                                 waterfront_type="oceanfront", city="Fort Lauderdale",
                                 direction="east", floor=42, building_slug="brickell-tower-a")
        assert manifest["building_slug"] == "brickell-tower-a"
        room = manifest["rooms"]["bed2"]
        assert room["panorama_url"]
        unit_dir = out / "continuum-residence-01"
        assert (unit_dir / "bed2.jpg").exists()
    finally:
        cfg.settings.out_dir = old


# --- API end-to-end --------------------------------------------------------

def test_api_job_creation_accepts_outlook_fields_end_to_end():
    project = client.post("/api/v1/projects", headers=_AUTH_HEADERS, data={"name": "Outlook API test"})
    assert project.status_code == 200
    pid = project.json()["project_id"]
    with PLAN.open("rb") as f:
        upload = client.post(f"/api/v1/projects/{pid}/floor-plan", headers=_AUTH_HEADERS,
                             files={"file": (PLAN.name, f, "image/jpeg")})
    assert upload.status_code == 200
    input_id = upload.json()["input_id"]

    r = client.post(f"/api/v1/projects/{pid}/jobs", headers=_AUTH_HEADERS, data={
        "input_id": input_id, "unit_id": "continuum-residence-01",
        "only": "bed2", "provider": "mock", "lighting": "sunset",
        "waterfront_type": "oceanfront", "city": "Fort Lauderdale",
        "direction": "east", "floor": "42", "building_slug": "brickell-tower-a",
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
    assert status["waterfront_type"] == "oceanfront"
    assert status["city"] == "Fort Lauderdale"
    assert status["direction"] == "east"
    assert status["floor"] == 42
    assert status["building_slug"] == "brickell-tower-a"
    assert status["manifest"]["building_slug"] == "brickell-tower-a"


def test_legacy_generate_route_accepts_outlook_fields_end_to_end():
    r = client.post("/units/continuum-residence-01/generate", data={
        "staged": "false", "only": "bed2", "provider": "mock", "lighting": "daylight",
        "waterfront_type": "intracoastal", "city": "Fort Lauderdale", "direction": "sw",
        "floor": "10", "building_slug": "brickell-tower-a",
    })
    assert r.status_code == 200
    jid = r.json()["job_id"]

    status = None
    for _ in range(300):
        status = client.get(f"/jobs/{jid}").json()
        if status["status"] in {"done", "error"}:
            break
        time.sleep(0.1)
    assert status["status"] == "done", status
    assert status["manifest"]["building_slug"] == "brickell-tower-a"


def test_legacy_generate_route_without_outlook_fields_is_unaffected():
    # The exact pre-existing call shape (no new fields at all) must still work.
    r = client.post("/units/continuum-residence-01/generate", data={
        "staged": "false", "only": "bed2", "provider": "mock",
    })
    assert r.status_code == 200
    jid = r.json()["job_id"]

    status = None
    for _ in range(300):
        status = client.get(f"/jobs/{jid}").json()
        if status["status"] in {"done", "error"}:
            break
        time.sleep(0.1)
    assert status["status"] == "done", status
    assert "building_slug" not in status["manifest"]
