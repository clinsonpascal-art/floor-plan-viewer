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
