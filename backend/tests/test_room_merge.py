"""Regression tests for room_segment's fragment-merge pass (see
room_segment._merge_small_fragments): a small polygon carved out of a
bigger room's interior - most of its own perimeter is wall shared with that
one neighbor - gets folded back into it, while two genuinely separate rooms
of comparable size, even though adjacent via an ordinary partition wall,
are left alone."""
from app import room_segment, wall_detect
from app.plan_geom_types import WallSegment
from app.plan_preprocess import _binarize

from fixtures.synthetic_plan import build_synthetic_plan


def _wall(id_, a, b, thickness=6.0):
    return WallSegment(id=id_, a_px=a, b_px=b, thickness_px=thickness, confidence=1.0)


def _two_room_plan_with_closet() -> list[WallSegment]:
    """Left room (180x260 = 46800px^2) | right room (180x260), with a 40x40
    closet notched into the right room's bottom-right corner: one edge
    (its bottom) sits on the shared exterior wall, the other three are new
    interior walls separating it from the rest of the right room's
    interior. A naive segmenter faces this as 3 regions instead of 2 rooms."""
    return [
        _wall("top", (20, 20), (380, 20)),
        _wall("right", (380, 20), (380, 280)),
        _wall("bottom", (20, 280), (380, 280)),
        _wall("left", (20, 280), (20, 20)),
        _wall("partition", (200, 20), (200, 280)),
        _wall("closet_top", (300, 240), (340, 240)),
        _wall("closet_left", (300, 240), (300, 280)),
        _wall("closet_right", (340, 240), (340, 280)),
    ]


def test_small_adjacent_closet_is_merged_into_parent_room():
    walls = _two_room_plan_with_closet()

    raw = room_segment.segment(walls, min_room_area_px2=500, merge_fragments=False)
    assert len(raw) == 3, "sanity check: this layout really does over-segment into 3 faces"
    assert min(r.area_px2 for r in raw) < 2000, "the closet face should be the small one"

    merged = room_segment.segment(walls, min_room_area_px2=500, merge_fragments=True)
    assert len(merged) == 2, "the closet must fold into the room it was carved out of"

    # Both rooms should now be back to ~46800px^2 (180x260) each - the
    # closet's area is recovered into its parent, not lost or duplicated.
    areas = sorted(r.area_px2 for r in merged)
    assert all(abs(a - 46800) / 46800 < 0.05 for a in areas), areas


def test_two_similarly_sized_adjacent_rooms_are_not_merged():
    """The plain two-equal-room synthetic layout (no closet) must come out
    unchanged: two genuinely separate rooms of comparable size sharing an
    ordinary partition wall are never folded together."""
    img = build_synthetic_plan()
    mask = _binarize(img, "otsu")
    walls = wall_detect.detect(mask, min_wall_len_px=40)

    rooms = room_segment.segment(walls, min_room_area_px2=500)
    assert len(rooms) == 2

    a, b = rooms[0].area_px2, rooms[1].area_px2
    ratio = min(a, b) / max(a, b)
    assert ratio > 0.9, "two genuinely separate, similarly sized rooms must stay separate"
