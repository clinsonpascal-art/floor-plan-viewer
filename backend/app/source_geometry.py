"""Convert annotated floor-plan regions into deterministic room-local geometry.

The supplied Continuum sheet is a raster screenshot, so this module preserves
source shape while keeping every derived measurement explicitly approximate.
It is intentionally deterministic and does not claim CAD accuracy.
"""
from __future__ import annotations

from math import hypot


def _close(points):
    if not points:
        return []
    return points if points[0] == points[-1] else points + [points[0]]


def polygon_to_local(points_px, bbox_px, width_ft, depth_ft):
    """Map a source polygon into a room-local x/y coordinate system in feet."""
    if not points_px or not bbox_px or not width_ft or not depth_ft:
        return None
    bx0, by0, bx1, by1 = bbox_px
    sx = max(1.0, bx1 - bx0)
    sy = max(1.0, by1 - by0)
    out = []
    for x, y in points_px:
        lx = (float(x) - bx0) / sx * float(width_ft)
        ly = (float(y) - by0) / sy * float(depth_ft)
        out.append([round(lx, 3), round(ly, 3)])
    return out


def walls_from_polygon(boundary, height_ft=11.0):
    if not boundary:
        return []
    pts = _close(boundary)
    walls = []
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        walls.append({
            "id": f"wall_{i+1:02d}",
            "a": [a[0], a[1], 0],
            "b": [b[0], b[1], 0],
            "height_ft": height_ft,
            "source": "annotated_plan_polygon",
        })
    return walls


def build_source_geometry(room: dict) -> dict | None:
    src = room.get("source_plan") or {}
    poly = room.get("source_polygon_px")
    if not src.get("bbox_px") or not poly:
        return None
    w = room.get("width_ft")
    d = room.get("length_ft")
    local = polygon_to_local(poly, src["bbox_px"], w, d)
    if not local:
        return None
    return {
        "coordinate_system": "room_local_ft",
        "source_fidelity": "source_shape_plus_inferred_3d_openings",
        "boundary": local,
        "walls": walls_from_polygon(local),
        "source_polygon_px": poly,
        "source_bbox_px": src["bbox_px"],
    }
