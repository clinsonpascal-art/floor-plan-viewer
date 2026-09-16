"""Deterministic wall-segment detection from a preprocessed binary plan mask.

Two complementary passes, merged:
  Pass A - directional morphological opening: robust for axis-aligned walls,
           suppresses text/furniture/door-arc noise (all short/compact).
  Pass B - probabilistic Hough transform: catches arbitrary-angle walls
           (e.g. a curved/angled terrace edge) Pass A's axis-aligned kernels miss.

No AI/vision-model call - pure OpenCV + numpy geometry.
"""
from __future__ import annotations

import math
import uuid

import cv2
import numpy as np

from .plan_geom_types import WallSegment


def _segments_from_mask_components(mask: np.ndarray, min_len_px: float) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """Pass A: long thin components via directional morphological opening."""
    k = max(3, int(round(min_len_px)))
    horiz_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k, 1))
    vert_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, k))
    horiz = cv2.morphologyEx(mask, cv2.MORPH_OPEN, horiz_kernel)
    vert = cv2.morphologyEx(mask, cv2.MORPH_OPEN, vert_kernel)
    wall_mask = cv2.bitwise_or(horiz, vert)

    contours, _ = cv2.findContours(wall_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    segments = []
    for cnt in contours:
        if cv2.contourArea(cnt) < 4:
            continue
        rect = cv2.minAreaRect(cnt)
        (cx, cy), (rw, rh), angle = rect
        if max(rw, rh) < min_len_px:
            continue
        # long axis endpoints
        long_len = max(rw, rh)
        theta = math.radians(angle if rw >= rh else angle + 90.0)
        dx, dy = math.cos(theta), math.sin(theta)
        half = long_len / 2.0
        a = (cx - dx * half, cy - dy * half)
        b = (cx + dx * half, cy + dy * half)
        segments.append((a, b))
    return segments


def _segments_from_hough(mask: np.ndarray, min_len_px: float) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """Pass B: arbitrary-angle lines via probabilistic Hough transform."""
    lines = cv2.HoughLinesP(
        mask, rho=1, theta=np.pi / 180, threshold=40,
        minLineLength=max(4, int(round(min_len_px))), maxLineGap=5,
    )
    if lines is None:
        return []
    flat = lines.reshape(-1, 4)  # cv2 4.x returns (N,1,4); cv2 5.x returns (N,4)
    return [((float(x0), float(y0)), (float(x1), float(y1))) for x0, y0, x1, y1 in flat]


def _angle_deg(a, b) -> float:
    return math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) % 180.0


def _sample_thickness(raw_mask: np.ndarray, a, b, n: int = 10) -> tuple[float, float]:
    """Sample perpendicular run-length of foreground pixels at n points along a-b.
    Returns (median_thickness_px, coverage_ratio)."""
    h, w = raw_mask.shape
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy)
    if length < 1e-6:
        return 0.0, 0.0
    ux, uy = dx / length, dy / length
    nx, ny = -uy, ux  # perpendicular unit vector
    thicknesses = []
    covered = 0
    for i in range(n):
        t = (i + 0.5) / n
        px, py = a[0] + ux * length * t, a[1] + uy * length * t
        run = 0
        for s in range(-20, 21):
            sx, sy = int(round(px + nx * s)), int(round(py + ny * s))
            if 0 <= sx < w and 0 <= sy < h and raw_mask[sy, sx] > 0:
                run += 1
        if run > 0:
            thicknesses.append(run)
            covered += 1
    coverage = covered / n
    if not thicknesses:
        return 0.0, coverage
    return float(np.median(thicknesses)), coverage


def _cluster_and_merge(
    segments: list[tuple[tuple[float, float], tuple[float, float]]],
    raw_mask: np.ndarray,
    angle_tol_deg: float = 4.0,
    perp_tol_px: float = 8.0,
) -> list[WallSegment]:
    """Cluster near-collinear segments and merge each cluster into one WallSegment."""
    remaining = list(segments)
    clusters: list[list[tuple[tuple[float, float], tuple[float, float]]]] = []

    while remaining:
        seed = remaining.pop(0)
        cluster = [seed]
        seed_angle = _angle_deg(*seed)
        seed_mid = ((seed[0][0] + seed[1][0]) / 2.0, (seed[0][1] + seed[1][1]) / 2.0)
        still = []
        for seg in remaining:
            ang = _angle_deg(*seg)
            d_ang = min(abs(ang - seed_angle), 180.0 - abs(ang - seed_angle))
            if d_ang > angle_tol_deg:
                still.append(seg)
                continue
            mid = ((seg[0][0] + seg[1][0]) / 2.0, (seg[0][1] + seg[1][1]) / 2.0)
            theta = math.radians(seed_angle)
            ux, uy = math.cos(theta), math.sin(theta)
            nx, ny = -uy, ux
            perp = abs((mid[0] - seed_mid[0]) * nx + (mid[1] - seed_mid[1]) * ny)
            if perp <= perp_tol_px:
                cluster.append(seg)
            else:
                still.append(seg)
        remaining = still
        clusters.append(cluster)

    walls: list[WallSegment] = []
    for cluster in clusters:
        pts = [p for seg in cluster for p in seg]
        angle = _angle_deg(*cluster[0])
        theta = math.radians(angle)
        ux, uy = math.cos(theta), math.sin(theta)
        ox, oy = pts[0]
        projections = [(p[0] - ox) * ux + (p[1] - oy) * uy for p in pts]
        t_min, t_max = min(projections), max(projections)
        a = (ox + ux * t_min, oy + uy * t_min)
        b = (ox + ux * t_max, oy + uy * t_max)

        thickness_px, coverage = _sample_thickness(raw_mask, a, b)
        if thickness_px <= 0:
            continue
        confidence = max(0.0, min(1.0, coverage))
        walls.append(WallSegment(
            id=f"wall_{uuid.uuid4().hex[:8]}",
            a_px=a, b_px=b,
            thickness_px=round(thickness_px, 2),
            confidence=round(confidence, 3),
        ))
    return walls


def detect(mask: np.ndarray, min_wall_len_px: float) -> list[WallSegment]:
    """Detect wall centerline segments from a preprocessed binary mask.

    mask: output of plan_preprocess.preprocess().mask (0/255, wall pixels=255).
    min_wall_len_px: shortest plausible wall, in pixels (derived from scale
      calibration - e.g. 2 ft * px_per_ft). Passing a fixed bootstrap value
      before scale is known is expected on the first pass (see plan_scale.py).
    """
    seg_a = _segments_from_mask_components(mask, min_wall_len_px)
    seg_b = _segments_from_hough(mask, min_wall_len_px)
    all_segments = seg_a + seg_b
    if not all_segments:
        return []
    return _cluster_and_merge(all_segments, mask)
