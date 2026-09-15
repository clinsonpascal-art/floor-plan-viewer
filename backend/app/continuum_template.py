"""Source-grounded room graph for Continuum Club & Residences, Tower Residence 01.

The uploaded sheet is a screenshot rather than CAD. Room dimensions below are
therefore *estimated from the visible plan footprint* unless the source sheet
prints a dimension. They are never represented as survey/CAD measurements.
"""
from __future__ import annotations

import math

from .continuum_plan import RESIDENCE_01_SOURCE_ROOMS, RESIDENCE_01_TERRACES

# The shared viewer (src/tour-template.html #mapsvg) draws the clickable minimap
# rect for each room from room.x/y/w/h, and each in-room doorway hotspot from
# link.px/py/chev. Those are hand-authored for Residence A; for this
# source-grounded unit they are derived from the same plan-pixel bboxes used
# for room dimensions, so the minimap and doorway hotspots are clickable
# instead of collapsing to a zero-size point.
_PLAN_W, _PLAN_H = 810.0, 490.0          # continuum_plan.PLAN_SIZE
_MAP_W, _MAP_H = 140.0, 160.0            # tour-template.html #mapsvg viewBox
_TERRACE_BBOX_PX = (390, 95, 800, 275)   # merged footprint of terraces A/B/C
_ROOM_BBOX_PX = {**{rid: tuple(item["bbox_px"]) for rid, item in RESIDENCE_01_SOURCE_ROOMS.items()},
                  "terrace": _TERRACE_BBOX_PX}

# 8-way compass bucket -> (chevron, hotspot px%, hotspot py%)
_COMPASS = [
    ("→", 85, 50), ("↘", 78, 78), ("↓", 50, 85), ("↙", 22, 78),
    ("←", 15, 50), ("↖", 22, 18), ("↑", 50, 15), ("↗", 78, 18),
]


def _center(bbox_px):
    x0, y0, x1, y1 = bbox_px
    return (x0 + x1) / 2, (y0 + y1) / 2


def _minimap_rect(bbox_px):
    x0, y0, x1, y1 = bbox_px
    return (round(x0 * _MAP_W / _PLAN_W, 1), round(y0 * _MAP_H / _PLAN_H, 1),
            round((x1 - x0) * _MAP_W / _PLAN_W, 1), round((y1 - y0) * _MAP_H / _PLAN_H, 1))


def _doorway_links(rid: str, links: list) -> list:
    a = _center(_ROOM_BBOX_PX[rid])
    seen = {}
    out = []
    for link in links:
        b = _center(_ROOM_BBOX_PX.get(link["to"], a))
        angle = math.atan2(b[1] - a[1], b[0] - a[0])  # screen coords: +y is down
        idx = round(angle / (math.pi / 4)) % 8
        chev, px, py = _COMPASS[idx]
        jitter = seen.get(idx, 0) * 8
        seen[idx] = seen.get(idx, 0) + 1
        out.append({**link, "chev": chev, "px": min(92, px + jitter), "py": py})
    return out


def _estimate_dims():
    # Calibrate the visible interior footprint against the printed 2,080 SF
    # interior area. This gives useful rendering proportions while retaining an
    # explicit "estimated" provenance flag.
    plan_w, plan_h = 565.0, 303.0
    sqft_per_px = 2080.0 / (plan_w * plan_h)
    out = {}
    for rid, item in RESIDENCE_01_SOURCE_ROOMS.items():
        x0, y0, x1, y1 = item["bbox_px"]
        pw, ph = max(1, x1-x0), max(1, y1-y0)
        area = pw * ph * sqft_per_px
        aspect = pw / ph
        width = (area * aspect) ** 0.5
        depth = area / width
        out[rid] = (round(width, 2), round(depth, 2))
    return out


DIMS = _estimate_dims()

CONTINUUM_RESIDENCE_01 = {
    "bed3": {"name": "Bedroom 3", "view": True, "view_wall": "west", "feat": "Third bedroom with terrace access and built-in storage",
             "links": [{"to": "bath3", "label": "Bath 3"}, {"to": "great", "label": "Living Room"}]},
    "bed2": {"name": "Bedroom 2", "view": True, "view_wall": "north", "feat": "Bay-facing bedroom with closet and Bath 2 nearby",
             "links": [{"to": "bath2", "label": "Bath 2"}, {"to": "great", "label": "Living Room"}]},
    "great": {"name": "Living Room", "view": True, "view_wall": "north", "feat": "Central living room opening toward the curved private terraces",
              "links": [{"to": "bed2", "label": "Bedroom 2"}, {"to": "bed3", "label": "Bedroom 3"},
                        {"to": "kitchen", "label": "Kitchen"}, {"to": "primary", "label": "Primary Bedroom"},
                        {"to": "terrace", "label": "Terrace"}]},
    "kitchen": {"name": "Kitchen", "view": False, "feat": "Central kitchen with island, cabinetry and appliance wall",
                 "links": [{"to": "great", "label": "Living Room"}, {"to": "primary", "label": "Primary Bedroom"}]},
    "primary": {"name": "Primary Bedroom", "view": True, "view_wall": "east", "feat": "Bay-facing primary suite with walk-in closet and direct Primary Bath connection",
                 "links": [{"to": "great", "label": "Living Room"}, {"to": "pbath", "label": "Primary Bath"}]},
    "pbath": {"name": "Primary Bath", "view": False, "feat": "Primary en-suite bath with dual vanity, tub and shower zone",
              "links": [{"to": "primary", "label": "Primary Bedroom"}]},
    "bath2": {"name": "Bath 2", "view": False, "feat": "En-suite / bedroom bath serving Bedroom 2",
              "links": [{"to": "bed2", "label": "Bedroom 2"}]},
    "bath3": {"name": "Bath 3", "view": False, "feat": "Bath serving Bedroom 3",
              "links": [{"to": "bed3", "label": "Bedroom 3"}]},
    "powder": {"name": "Powder Room", "view": False, "feat": "Guest powder room positioned along the interior circulation zone",
               "links": [{"to": "great", "label": "Living Room"}]},
    "terrace": {"name": "Private Terrace", "view": True, "feat": "Large private outdoor terrace wrapping the curved residence edge",
                 "links": [{"to": "great", "label": "Living Room"}]},
}


def build_template():
    result = {}
    for rid, base in CONTINUUM_RESIDENCE_01.items():
        r = dict(base)
        if rid in DIMS:
            w, d = DIMS[rid]
            r["width_ft"], r["length_ft"] = w, d
            r["dim"] = f"≈ {w:g}′ × {d:g}′"
            r["dimension_source"] = "estimated_from_visible_plan_and_printed_total_area"
        else:
            # Terrace is intentionally not assigned a fake room dimension.
            r["width_ft"] = None
            r["length_ft"] = None
            r["dim"] = "Approximate terrace footprint from plan"
            r["dimension_source"] = "visible_plan_region_only"
        r["x"], r["y"], r["w"], r["h"] = _minimap_rect(_ROOM_BBOX_PX.get(rid, _TERRACE_BBOX_PX))
        r["links"] = _doorway_links(rid, r["links"])
        if rid in RESIDENCE_01_SOURCE_ROOMS:
            r["source_polygon_px"] = RESIDENCE_01_SOURCE_ROOMS[rid].get("polygon_px") or [
                [RESIDENCE_01_SOURCE_ROOMS[rid]["bbox_px"][0], RESIDENCE_01_SOURCE_ROOMS[rid]["bbox_px"][1]],
                [RESIDENCE_01_SOURCE_ROOMS[rid]["bbox_px"][2], RESIDENCE_01_SOURCE_ROOMS[rid]["bbox_px"][1]],
                [RESIDENCE_01_SOURCE_ROOMS[rid]["bbox_px"][2], RESIDENCE_01_SOURCE_ROOMS[rid]["bbox_px"][3]],
                [RESIDENCE_01_SOURCE_ROOMS[rid]["bbox_px"][0], RESIDENCE_01_SOURCE_ROOMS[rid]["bbox_px"][3]],
            ]
        elif rid == "terrace":
            r["source_polygon_px"] = [
                [390,95],[800,95],[800,275],[640,275],[640,155],[390,155]
            ]
        result[rid] = r
    return result
