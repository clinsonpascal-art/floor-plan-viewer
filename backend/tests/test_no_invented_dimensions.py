"""Regression test: a room with no legible printed dimension (e.g. from an
arbitrary uploaded floor plan where the vision model marked
dimension_source="not_available") must never be assigned a fabricated
width/depth, and must never get a structural control image built from one.

Before this fix, room_geometry.build_room_geometry() and
geometry.control_for_room() both silently defaulted an unmeasured room to
12ft x 14ft - a fabricated number presented as real geometry in the API
response and baked into the generated image's structural conditioning."""
from app.room_geometry import build_room_geometry
from app.geometry import control_for_room
from app.continuum_template import build_template


def _unmeasured_room(**overrides):
    room = {
        "id": "unlabeled_room", "name": "Unlabeled Room",
        "width_ft": None, "length_ft": None,
        "dimension_source": "not_available", "view": False, "links": [],
    }
    room.update(overrides)
    return room


def test_geometry_does_not_fabricate_dimensions_when_unmeasured():
    geom = build_room_geometry(_unmeasured_room())
    assert geom["width_ft"] is None
    assert geom["depth_ft"] is None
    assert geom["boundary"] is None
    assert geom["walls"] == []
    assert geom["doors"] == []
    assert geom["windows"] == []
    assert geom["source_fidelity"] == "dimensions_not_available_no_geometry_generated"
    assert geom["dimension_provenance"] == "not_available"


def test_no_structural_control_image_when_unmeasured():
    for mode in ("depth", "canny", "lineart"):
        assert control_for_room(_unmeasured_room(), mode) is None


def test_room_with_only_one_dimension_known_is_not_treated_as_unmeasured():
    # A room with e.g. only a printed width (length illegible) still has a
    # real, partial measurement - it should NOT be flattened to "unmeasured".
    room = _unmeasured_room(width_ft=10.0, length_ft=None, dimension_source="printed_on_uploaded_plan")
    geom = build_room_geometry(room)
    assert geom["width_ft"] == 10.0
    assert geom["depth_ft"] == 10.0  # falls back to the one known dimension, not a fabricated one
    assert geom["source_fidelity"] != "dimensions_not_available_no_geometry_generated"


def test_known_unit_rooms_with_real_dimensions_are_unaffected():
    """Every measured room in the known-unit templates keeps its existing
    behavior exactly - this fix only changes what happens for a room with
    no real dimension at all."""
    template = build_template()
    for rid, room in template.items():
        if not room.get("width_ft") and not room.get("length_ft"):
            continue  # e.g. terrace - deliberately unmeasured, covered separately below
        geom = build_room_geometry({**room, "id": rid})
        assert geom["width_ft"] is not None
        assert geom["depth_ft"] is not None
        assert geom["source_fidelity"] != "dimensions_not_available_no_geometry_generated"
        control = control_for_room({**room, "id": rid}, "depth")
        assert control is not None


def test_continuum_terrace_no_longer_gets_a_fabricated_dimension():
    """continuum_template.py already documents that the terrace's footprint
    is intentionally left unmeasured ("not assigned a fake room dimension").
    Before this fix, build_room_geometry/control_for_room silently fabricated
    12x14 for it anyway. Confirm that's now honestly reported instead."""
    template = build_template()
    terrace = {**template["terrace"], "id": "terrace"}
    assert not terrace.get("width_ft") and not terrace.get("length_ft")
    geom = build_room_geometry(terrace)
    assert geom["width_ft"] is None
    assert geom["depth_ft"] is None
    assert control_for_room(terrace, "depth") is None
