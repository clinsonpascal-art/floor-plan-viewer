"""Phase 4 integration test: the full deterministic detection orchestrator
(plan_detect.detect_plan) against the synthetic two-room fixture with known
wall/room/opening ground truth. Exercises the actual wiring end to end,
not just the individual phase modules in isolation.
"""
import cv2

from app import plan_detect, plan_scale

from fixtures.synthetic_plan import build_synthetic_plan_with_openings


def _write_fixture(tmp_path):
    img = build_synthetic_plan_with_openings()
    path = tmp_path / "synthetic_plan.png"
    cv2.imwrite(str(path), img)
    return path


def test_detects_rooms_walls_and_openings_without_a_scale_reference(tmp_path):
    """No printed dimension text and no manual/area reference is available for
    this fixture - dimensions must be honestly reported as unavailable, never
    fabricated, while shape/opening detection still works."""
    path = _write_fixture(tmp_path)
    result = plan_detect.detect_plan(path)

    assert result.scale is None
    assert "no_scale_reference_dimensions_unavailable" in result.warnings
    assert len(result.rooms) == 2
    assert len(result.walls) >= 4

    for room in result.rooms:
        width_ft, depth_ft = plan_detect.room_dimensions_ft(room, result.scale)
        assert width_ft is None and depth_ft is None

    # The door in the partition wall must connect the two rooms it separates.
    conn = plan_detect.infer_connections(result.rooms, result.openings)
    assert len(result.rooms) == 2
    r0, r1 = result.rooms
    assert r1.id in conn[r0.id]
    assert r0.id in conn[r1.id]


def test_manual_scale_yields_real_measured_dimensions_not_fabricated(tmp_path):
    """When a real scale reference IS available, dimensions must reflect the
    actual detected geometry (matching the fixture's known 180x260px rooms at
    a known px_per_ft), not a generic invented size."""
    path = _write_fixture(tmp_path)
    scale = plan_scale.calibrate_from_known_px_per_ft(10.0)  # 10 px == 1 ft
    result = plan_detect.detect_plan(path, manual_scale=scale)

    assert result.scale is scale
    assert len(result.rooms) == 2
    for room in result.rooms:
        width_ft, depth_ft = plan_detect.room_dimensions_ft(room, result.scale)
        assert width_ft is not None and depth_ft is not None
        # Each room is nominally 180x260px -> 18x26ft at 10px/ft; allow for
        # detection noise from wall thickness/endpoint snapping.
        assert 15.0 <= width_ft <= 21.0
        assert 23.0 <= depth_ft <= 29.0


def test_no_walls_no_hallucinated_rooms(tmp_path):
    """A blank image (no wall ink at all) must report zero rooms/openings and
    flag it, never fabricate a plausible-looking layout."""
    import numpy as np
    blank = np.full((300, 400), 255, dtype="uint8")
    path = tmp_path / "blank.png"
    cv2.imwrite(str(path), blank)

    result = plan_detect.detect_plan(path)
    assert result.walls == []
    assert result.rooms == []
    assert result.openings == []
    assert "no_walls_detected" in result.warnings
