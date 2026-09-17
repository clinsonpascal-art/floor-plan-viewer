"""Phase 2 accuracy test: opening (door/window) detection, against the
synthetic fixture with known door/window ground truth (see
fixtures/synthetic_plan.py::build_synthetic_plan_with_openings).

No AI vision/generative model - pure OpenCV + numpy geometry, same
constraint as wall_detect.py/room_segment.py.
"""
import math

from app import opening_detect, wall_detect
from app.plan_preprocess import _binarize

from fixtures.synthetic_plan import (
    DOOR_GAP_PX,
    PARTITION_X,
    WINDOW_GAP_PX,
    build_synthetic_plan_with_openings,
)

# Nominal absolute midpoints. WINDOW_GAP_PX/DOOR_GAP_PX are themselves already
# absolute image coordinates (see fixtures/synthetic_plan.py), not offsets
# from the wall's own start point.
_WINDOW_TARGET = ((WINDOW_GAP_PX[0] + WINDOW_GAP_PX[1]) / 2, 20)
_DOOR_TARGET = (PARTITION_X, (DOOR_GAP_PX[0] + DOOR_GAP_PX[1]) / 2)


def _detect():
    img = build_synthetic_plan_with_openings()
    mask = _binarize(img, "otsu")
    walls = wall_detect.detect(mask, min_wall_len_px=40)
    openings = opening_detect.detect_openings(walls, mask, img, px_per_ft=None)
    walls_by_id = {w.id: w for w in walls}
    return openings, walls_by_id


def _abs_point(opening, walls_by_id):
    """Convert a wall-relative offset back to an absolute (x, y) image point,
    using the WALL's own detected endpoints (whichever way they point) -
    not an assumed nominal direction."""
    wall = walls_by_id[opening.wall_id]
    ax, ay = wall.a_px
    bx, by = wall.b_px
    length = math.hypot(bx - ax, by - ay)
    ux, uy = (bx - ax) / length, (by - ay) / length
    t = opening.offset_px + opening.width_px / 2
    return (ax + ux * t, ay + uy * t)


def _dist(p, q):
    return math.hypot(p[0] - q[0], p[1] - q[1])


def _closest(openings, walls_by_id, target_xy):
    return min(openings, key=lambda o: _dist(_abs_point(o, walls_by_id), target_xy))


def test_window_gap_is_found_and_correctly_classified():
    openings, walls_by_id = _detect()
    match = _closest(openings, walls_by_id, _WINDOW_TARGET)

    expected_width = WINDOW_GAP_PX[1] - WINDOW_GAP_PX[0]
    assert _dist(_abs_point(match, walls_by_id), _WINDOW_TARGET) < 6.0
    assert abs(match.width_px - expected_width) < 6.0
    assert match.kind == "window"
    assert match.detection_method == "window_line_symbol"
    # A real window-glazing tick was matched, not just a bare gap.
    assert match.confidence > 0.5


def test_door_gap_is_found_at_the_correct_position_even_if_type_is_uncertain():
    """The door's swing arc is drawn touching the wall stub at the jamb, so
    its contour merges with the wall rather than forming a clean isolated
    circle - a real limitation of contour-based arc matching, not a bug.
    What matters for "no hallucinations": the opening's real position/width
    must still be found, and its type must never be reported as the WRONG
    kind (e.g. mislabeled "window") - "door" or the honest "unknown_opening"
    are both acceptable outcomes; a wrong positive is not."""
    openings, walls_by_id = _detect()
    match = _closest(openings, walls_by_id, _DOOR_TARGET)

    expected_width = DOOR_GAP_PX[1] - DOOR_GAP_PX[0]
    assert _dist(_abs_point(match, walls_by_id), _DOOR_TARGET) < 6.0
    assert abs(match.width_px - expected_width) < 6.0
    assert match.kind in ("door", "unknown_opening")
    assert match.kind != "window"


def test_no_openings_are_invented_far_from_a_real_gap():
    """The two side walls (left/right/bottom) have no gaps cut into them at
    all - detection must not invent a confident door/window where there
    isn't one."""
    openings, walls_by_id = _detect()
    for o in openings:
        if o.kind in ("door", "window"):
            p = _abs_point(o, walls_by_id)
            nearest = min(_dist(p, _WINDOW_TARGET), _dist(p, _DOOR_TARGET))
            assert nearest < 20.0, (
                f"unexpected confident {o.kind} detection far from any real opening (point={p})"
            )
