"""Synthetic floor-plan raster generator with exact, known ground truth.

The real uploaded plan (source_continuum_residence_01.jpg) is a stylized,
ornate rendering (furniture icons, hatching, curved terrace) that cannot be
hand-annotated to pixel-exact ground truth by eyeballing a screenshot -
doing so would produce test assertions graded against fabricated numbers,
which defeats the point of a deterministic accuracy test.

Instead, Phase 1's accuracy-graded tests run against a synthetic plan built
here: a simple two-room rectangular floor plan whose wall centerlines and
room boundaries are known exactly, because this module drew them. The real
uploaded plan is exercised separately as a smoke test only (see
test_room_segment.py::test_real_plan_smoke) - sanity-checked, not
accuracy-graded.
"""
from __future__ import annotations

import cv2
import numpy as np

# Nominal (exact) wall centerlines, in pixels.
OUTER = (20, 20, 380, 280)   # x0, y0, x1, y1
PARTITION_X = 200
WALL_THICKNESS_PX = 6

EXPECTED_WALLS = [
    ((20, 20), (380, 20)),    # top
    ((380, 20), (380, 280)),  # right
    ((380, 280), (20, 280)),  # bottom
    ((20, 280), (20, 20)),    # left
    ((200, 20), (200, 280)),  # partition
]

EXPECTED_ROOMS = [
    [(20, 20), (200, 20), (200, 280), (20, 280)],    # left room
    [(200, 20), (380, 20), (380, 280), (200, 280)],  # right room
]


def build_synthetic_plan() -> np.ndarray:
    """Returns a grayscale uint8 image (white background, black wall lines)."""
    img = np.full((300, 400), 255, dtype=np.uint8)
    x0, y0, x1, y1 = OUTER
    cv2.rectangle(img, (x0, y0), (x1, y1), color=0, thickness=WALL_THICKNESS_PX)
    cv2.line(img, (PARTITION_X, y0), (PARTITION_X, y1), color=0, thickness=WALL_THICKNESS_PX)
    return img


# --- Phase 2 fixture: same layout, plus one door and one window with known
# ground truth, for opening-detection tests. A separate function so the
# existing Phase 1 fixture/tests above are completely untouched. ---
DOOR_WALL = "partition"      # gap in the partition wall
DOOR_GAP_PX = (140, 170)     # (y0, y1) absolute image coordinates
DOOR_JAMB = (PARTITION_X, DOOR_GAP_PX[0])
DOOR_RADIUS_PX = DOOR_GAP_PX[1] - DOOR_GAP_PX[0]

WINDOW_WALL = "top"           # gap in the top (outer) wall
WINDOW_GAP_PX = (280, 310)    # (x0, x1) absolute image coordinates


def build_synthetic_plan_with_openings() -> np.ndarray:
    """Same two-room layout as build_synthetic_plan(), with one door gap
    (partition wall, plus a quarter-circle swing arc) and one window gap
    (top wall, plus a perpendicular mullion tick) cut in - both with known
    pixel ground truth (DOOR_GAP_PX/WINDOW_GAP_PX above)."""
    img = build_synthetic_plan()

    # Door: erase a span of the partition wall, then draw a swing arc whose
    # radius equals the gap width, hinged at the near jamb - exactly the
    # symbol _classify_door_arc looks for.
    y0, y1 = DOOR_GAP_PX
    cv2.rectangle(img, (PARTITION_X - WALL_THICKNESS_PX, y0 - 1),
                  (PARTITION_X + WALL_THICKNESS_PX, y1 + 1), color=255, thickness=-1)
    cv2.ellipse(img, DOOR_JAMB, (DOOR_RADIUS_PX, DOOR_RADIUS_PX), 0, 0, 90, color=0, thickness=2)

    # Window: erase a span of the top wall, then draw one short perpendicular
    # tick across the gap - the conventional glazing mark _classify_window_line
    # looks for.
    x0, x1 = WINDOW_GAP_PX
    cv2.rectangle(img, (x0 - 1, 20 - WALL_THICKNESS_PX), (x1 + 1, 20 + WALL_THICKNESS_PX), color=255, thickness=-1)
    mid_x = (x0 + x1) // 2
    cv2.line(img, (mid_x, 20 - WALL_THICKNESS_PX - 2), (mid_x, 20 + WALL_THICKNESS_PX + 2), color=0, thickness=1)

    return img
