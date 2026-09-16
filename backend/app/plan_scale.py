"""Deterministic px->ft scale calibration for an uploaded floor-plan image.

No AI vision/generative model. Three methods, in priority order:
  1. manual_reference  - operator-supplied reference (two points + known ft length,
                          or an already-known px_per_ft). Purely deterministic.
  2. dimension_text_ocr - classical OCR (pytesseract character recognition, not a
                          vision-language model) reads printed dimension strings
                          and cross-checks them against detected wall lengths.
  3. total_area_anchor - printed total sqft vs. detected free-space area in px^2.
                          Lowest confidence; calibrates area, not linear scale.
"""
from __future__ import annotations

import math
import re
import statistics

from .plan_geom_types import ScaleCalibration, WallSegment

_DIM_RE = re.compile(r"(\d+)\s*[\'′]\s*-?\s*(\d{1,2})?\s*[\"″]?")


def calibrate_from_reference(p1_px: tuple[float, float], p2_px: tuple[float, float], known_ft: float) -> ScaleCalibration:
    if known_ft <= 0:
        raise ValueError("known_ft must be positive")
    dist_px = math.hypot(p2_px[0] - p1_px[0], p2_px[1] - p1_px[1])
    return ScaleCalibration(px_per_ft=dist_px / known_ft, source="manual_reference", confidence=1.0)


def calibrate_from_known_px_per_ft(px_per_ft: float) -> ScaleCalibration:
    return ScaleCalibration(px_per_ft=px_per_ft, source="manual_reference", confidence=1.0)


def _parse_dimension_text(text: str) -> float | None:
    """Parse a printed dimension string like 12'-6" or 12'6 into feet."""
    m = _DIM_RE.search(text)
    if not m:
        return None
    feet = int(m.group(1))
    inches = int(m.group(2)) if m.group(2) else 0
    return feet + inches / 12.0


def calibrate_from_ocr(gray, walls: list[WallSegment], min_matches: int = 3) -> ScaleCalibration | None:
    """Method 2: OCR dimension text, cross-checked against detected wall lengths.

    Returns None if pytesseract isn't installed or too few confident matches
    are found - caller should fall back to Method 3 or a manual reference.
    """
    try:
        import pytesseract
    except ImportError:
        return None

    data = pytesseract.image_to_data(gray, output_type=pytesseract.Output.DICT)
    ratios = []
    n = len(data.get("text", []))
    for i in range(n):
        text = (data["text"][i] or "").strip()
        ft_value = _parse_dimension_text(text)
        if not ft_value:
            continue
        tx = data["left"][i] + data["width"][i] / 2.0
        ty = data["top"][i] + data["height"][i] / 2.0
        text_is_horizontal = data["width"][i] >= data["height"][i]

        best_wall, best_dist = None, float("inf")
        for wall in walls:
            mx = (wall.a_px[0] + wall.b_px[0]) / 2.0
            my = (wall.a_px[1] + wall.b_px[1]) / 2.0
            wall_horizontal = abs(wall.b_px[0] - wall.a_px[0]) >= abs(wall.b_px[1] - wall.a_px[1])
            if wall_horizontal != text_is_horizontal:
                continue
            d = math.hypot(mx - tx, my - ty)
            if d < best_dist:
                best_dist, best_wall = d, wall
        if best_wall is None or best_dist > 150:
            continue
        ratios.append(best_wall.length_px() / ft_value)

    if len(ratios) < min_matches:
        return None
    median = statistics.median(ratios)
    filtered = [r for r in ratios if abs(r - median) / median < 0.20] or ratios
    px_per_ft = statistics.median(filtered)
    confidence = min(1.0, 0.5 + 0.1 * len(filtered))
    return ScaleCalibration(px_per_ft=px_per_ft, source="dimension_text_ocr",
                             confidence=round(confidence, 3), sample_count=len(filtered))


def calibrate_from_total_area(total_sqft: float, detected_area_px2: float) -> ScaleCalibration:
    """Method 3 (fallback, lowest confidence): calibrates area, not linear scale."""
    if total_sqft <= 0 or detected_area_px2 <= 0:
        raise ValueError("total_sqft and detected_area_px2 must be positive")
    px_per_ft = math.sqrt(detected_area_px2 / total_sqft)
    return ScaleCalibration(px_per_ft=px_per_ft, source="total_area_anchor", confidence=0.4)
