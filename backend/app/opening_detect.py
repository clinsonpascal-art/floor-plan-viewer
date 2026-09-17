"""Deterministic door/window/opening detection from a preprocessed floor-plan
mask and wall segments (Phase 2). No AI vision/generative model - pure
OpenCV + numpy geometry, same constraint as wall_detect.py/room_segment.py.

A wall is treated as one continuous partition (Phase 1); an opening is a gap
in that wall's own pixel coverage, detected here as metadata attached to the
wall - never a topological break affecting room segmentation.
"""
from __future__ import annotations

import math
import uuid

import cv2
import numpy as np

from .plan_geom_types import Opening, WallSegment


def _sample_density_profile(raw_mask: np.ndarray, a, b, thickness_px: float, n: int):
    """Foreground-pixel density at n points along the wall's own corridor.

    Vectorized over both the n sample points and the perpendicular scan (a
    naive double python loop here is the dominant cost on a real, many-wall
    plan - profiled at ~3s alone on the Continuum sample)."""
    h, w = raw_mask.shape
    length = math.hypot(b[0] - a[0], b[1] - a[1])
    if length < 1e-6:
        return []
    ux, uy = (b[0] - a[0]) / length, (b[1] - a[1]) / length
    nx, ny = -uy, ux
    half = max(2.0, thickness_px / 2.0 + 2.0)
    steps = np.arange(-half, half + 1.0, 1.0)  # matches the old while s<=half: ...; s+=1.0

    t = np.linspace(0.0, 1.0, n)
    px = a[0] + ux * length * t
    py = a[1] + uy * length * t

    sx = np.rint(px[:, None] + nx * steps[None, :]).astype(np.int64)
    sy = np.rint(py[:, None] + ny * steps[None, :]).astype(np.int64)
    in_bounds = (sx >= 0) & (sx < w) & (sy >= 0) & (sy < h)
    sx_c, sy_c = np.clip(sx, 0, w - 1), np.clip(sy, 0, h - 1)
    hits = ((raw_mask[sy_c, sx_c] > 0) & in_bounds).sum(axis=1)
    return (hits / steps.size).tolist()


def _find_gap_intervals(profile: list[float], length_px: float, density_threshold: float = 0.3,
                         bridge_px: float = 6.0):
    """Run-length-encode low-density columns into (start_t, end_t) gap
    intervals. A short foreground interruption inside a gap (e.g. a window's
    own glazing/mullion tick drawn across the opening) is bridged rather than
    splitting one real opening into two - the interruption is real ink, but
    it belongs to the opening's own symbol, not to a wall on either side."""
    n = len(profile)
    if n == 0:
        return []
    is_gap = [p < density_threshold for p in profile]
    px_per_sample = length_px / max(1, n - 1)
    bridge_samples = max(1, round(bridge_px / max(px_per_sample, 1e-6)))

    i = 0
    while i < n:
        if not is_gap[i]:
            j = i
            while j < n and not is_gap[j]:
                j += 1
            run_len = j - i
            interrupts_a_gap = i > 0 and j < n and is_gap[i - 1] and is_gap[j]
            if interrupts_a_gap and run_len <= bridge_samples:
                for k in range(i, j):
                    is_gap[k] = True
            i = j
        else:
            i += 1

    intervals = []
    i = 0
    while i < n:
        if is_gap[i]:
            j = i
            while j < n and is_gap[j]:
                j += 1
            t0, t1 = i / (n - 1) if n > 1 else 0, (j - 1) / (n - 1) if n > 1 else 0
            intervals.append((t0 * length_px, t1 * length_px))
            i = j
        else:
            i += 1
    return intervals


def _classify_door_arc(gray: np.ndarray, center_px, radius_hint_px: float) -> tuple[bool, float]:
    """Look for a door-swing arc: a contour whose fitted circle radius is
    close to the gap width and whose fit residual is low."""
    x, y = int(center_px[0]), int(center_px[1])
    pad = int(radius_hint_px * 1.6) + 5
    h, w = gray.shape
    x0, y0 = max(0, x - pad), max(0, y - pad)
    x1, y1 = min(w, x + pad), min(h, y + pad)
    if x1 <= x0 or y1 <= y0:
        return False, 0.0
    crop = gray[y0:y1, x0:x1]
    if crop.size == 0:
        return False, 0.0
    _, mask = cv2.threshold(crop, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    min_arc_points = max(10, int(radius_hint_px * 0.9))  # a real ~90 deg arc has ~ (pi/2)*r points
    best_score = 0.0
    for cnt in contours:
        if len(cnt) < min_arc_points:
            continue
        (cx, cy), r = cv2.minEnclosingCircle(cnt)
        if r < 2 or not (0.6 * radius_hint_px <= r <= 1.4 * radius_hint_px):
            continue
        pts = cnt.reshape(-1, 2).astype(np.float64)
        dists = np.sqrt((pts[:, 0] - cx) ** 2 + (pts[:, 1] - cy) ** 2)
        residual = float(np.std(dists) / max(r, 1e-6))
        if residual > 0.2:
            continue
        # Angular span: a real door-swing arc sweeps roughly a quarter turn.
        # Computed as 360 minus the largest gap between consecutive sorted
        # angles (mod 360), so an arc straddling the 0/360 wraparound point
        # is still measured correctly - a naive max-minus-min is not.
        angles = np.sort(np.degrees(np.arctan2(pts[:, 1] - cy, pts[:, 0] - cx)) % 360)
        gaps = np.diff(np.concatenate([angles, angles[:1] + 360]))
        span = 360.0 - float(np.max(gaps))
        if not (60.0 <= span <= 130.0):
            continue
        score = max(0.0, 1.0 - residual)
        best_score = max(best_score, score)
    return best_score > 0, best_score


def _classify_window_line(gray: np.ndarray, center_px, wall_angle_deg: float, gap_width_px: float) -> tuple[bool, float]:
    """Look for a thin line roughly perpendicular to the wall, spanning the
    gap - the conventional glazing/mullion mark across a window opening."""
    x, y = int(center_px[0]), int(center_px[1])
    pad = int(gap_width_px * 0.7) + 5
    h, w = gray.shape
    x0, y0 = max(0, x - pad), max(0, y - pad)
    x1, y1 = min(w, x + pad), min(h, y + pad)
    if x1 <= x0 or y1 <= y0:
        return False, 0.0
    crop = gray[y0:y1, x0:x1]
    if crop.size == 0:
        return False, 0.0
    _, mask = cv2.threshold(crop, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    lines = cv2.HoughLinesP(mask, 1, np.pi / 180, threshold=8, minLineLength=3, maxLineGap=2)
    if lines is None:
        return False, 0.0
    perp_target = (wall_angle_deg + 90.0) % 180.0
    best_score = 0.0
    for x0l, y0l, x1l, y1l in lines.reshape(-1, 4):
        ang = math.degrees(math.atan2(y1l - y0l, x1l - x0l)) % 180.0
        diff = min(abs(ang - perp_target), 180.0 - abs(ang - perp_target))
        if diff <= 12.0:
            best_score = max(best_score, 1.0 - diff / 12.0)
    return best_score > 0, best_score


def detect_openings(walls: list[WallSegment], raw_mask: np.ndarray, gray: np.ndarray,
                     px_per_ft: float | None, min_opening_ft: float = 1.2, max_opening_ft: float = 20.0) -> list[Opening]:
    """Detect openings (gaps) along each wall. If px_per_ft is unknown, width
    filtering falls back to a plausible pixel-only heuristic (a fraction of
    the wall's own length) since we cannot convert to feet without a scale."""
    openings: list[Opening] = []
    for wall in walls:
        length_px = wall.length_px()
        if length_px < 4:
            continue
        profile = _sample_density_profile(raw_mask, wall.a_px, wall.b_px, wall.thickness_px, n=max(8, int(length_px)))
        gaps = _find_gap_intervals(profile, length_px)

        if px_per_ft:
            min_w, max_w = min_opening_ft * px_per_ft, max_opening_ft * px_per_ft
        else:
            min_w, max_w = max(4.0, length_px * 0.03), length_px * 0.9

        ux = (wall.b_px[0] - wall.a_px[0]) / length_px
        uy = (wall.b_px[1] - wall.a_px[1]) / length_px
        wall_angle = math.degrees(math.atan2(uy, ux)) % 180.0

        for t0, t1 in gaps:
            width_px = t1 - t0
            if width_px < min_w or width_px > max_w:
                continue
            mid_t = (t0 + t1) / 2.0
            center = (wall.a_px[0] + ux * mid_t, wall.a_px[1] + uy * mid_t)

            is_door, door_score = _classify_door_arc(gray, center, width_px)
            is_window, window_score = (False, 0.0)
            if not is_door:
                is_window, window_score = _classify_window_line(gray, center, wall_angle, width_px)

            if is_door:
                kind, method, confidence = "door", "swing_arc_fit", door_score
            elif is_window:
                kind, method, confidence = "window", "window_line_symbol", window_score
            else:
                kind, method, confidence = "unknown_opening", "gap_only", 0.4

            openings.append(Opening(
                id=f"opening_{uuid.uuid4().hex[:8]}",
                wall_id=wall.id,
                kind=kind,
                offset_px=round(t0, 2),
                width_px=round(width_px, 2),
                confidence=round(confidence, 3),
                detection_method=method,
            ))
    return openings
