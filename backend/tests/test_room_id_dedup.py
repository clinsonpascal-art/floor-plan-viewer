"""Regression test for a room-to-rendering mapping bug: analyze.get_rooms()'s
uploaded-plan branch used to key every room purely by the vision-parsed id
with no uniqueness check. Two distinct rooms that slugify to the same id
(e.g. two ambiguously/identically named regions) silently collided - the
second room's render overwrote the first's output file, and both order[]
entries pointed at the same manifest node/panorama_url. Fixed in
analyze.get_rooms() by disambiguating repeated ids (bath, bath_2, ...)."""
from pathlib import Path
from unittest.mock import patch

import app.config as cfg
from app.pipeline import generate_unit

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "source_continuum_residence_01.jpg"

# Two rooms the vision parser assigns the identical id "bath" to (this is
# exactly the ambiguous-naming case a real vision response can produce),
# plus one distinct room.
_DUPLICATE_ID_PARSE_RESULT = [
    {"id": "bath", "name": "Bath", "width_ft": 8, "length_ft": 6, "bbox_norm": [0.1, 0.1, 0.3, 0.3],
     "polygon_norm": [], "view_wall": None, "connections": [], "dimension_source": "printed_on_uploaded_plan"},
    {"id": "bath", "name": "Bath", "width_ft": 7, "length_ft": 9, "bbox_norm": [0.5, 0.5, 0.7, 0.7],
     "polygon_norm": [], "view_wall": None, "connections": [], "dimension_source": "printed_on_uploaded_plan"},
    {"id": "great", "name": "Great Room", "width_ft": 18, "length_ft": 15, "bbox_norm": [0.0, 0.0, 0.5, 0.5],
     "polygon_norm": [], "view_wall": "south", "connections": [], "dimension_source": "printed_on_uploaded_plan"},
]


def test_colliding_room_ids_get_unique_renders_not_overwritten():
    out = ROOT / "renders_dedup_test"
    old = cfg.settings.out_dir
    cfg.settings.out_dir = str(out)
    try:
        with patch("app.analyze.parse_uploaded_plan", return_value=_DUPLICATE_ID_PARSE_RESULT):
            manifest = generate_unit("dedup-test-unit", PLAN, provider="mock")

        # All three parsed rooms must be distinct entries - none silently
        # dropped/overwritten because their ids collided.
        assert len(manifest["order"]) == 3
        assert len(set(manifest["order"])) == 3, "order must not contain duplicate ids"
        assert len(manifest["rooms"]) == 3

        # Every room must have its own, distinct panorama_url and file.
        urls = [manifest["rooms"][rid]["panorama_url"] for rid in manifest["order"]]
        assert len(set(urls)) == 3, "each room must point at its own rendered asset, not a shared one"
        for rid in manifest["order"]:
            assert (out / "dedup-test-unit" / f"{rid}.jpg").exists()

        # The disambiguated id keeps the room's original display name/dims -
        # only the internal id was made unique, nothing about the room itself
        # (name, dimensions) was altered.
        assert manifest["rooms"]["bath"]["dim"].startswith("8")
        assert manifest["rooms"]["bath_2"]["dim"].startswith("7")
    finally:
        cfg.settings.out_dir = old
