"""Room-local geometry for the floor-plan-to-render pipeline.

Source-grounded rooms prefer the polygon traced from the supplied Continuum
floor-plan screenshot. Because the source is a raster screenshot, the 3D
opening positions remain explicitly inferred until CAD/vector data is available.
"""
from __future__ import annotations

from .source_geometry import build_source_geometry


def _opening_id(prefix: str, n: int) -> str:
    return f"{prefix}_{n:02d}"


def _rect_walls(w: float, d: float, h: float):
    return [
        {"id": "wall_north", "a": [0, 0, 0], "b": [w, 0, 0], "height_ft": h, "source": "inferred_rectangle"},
        {"id": "wall_east", "a": [w, 0, 0], "b": [w, d, 0], "height_ft": h, "source": "inferred_rectangle"},
        {"id": "wall_south", "a": [w, d, 0], "b": [0, d, 0], "height_ft": h, "source": "inferred_rectangle"},
        {"id": "wall_west", "a": [0, d, 0], "b": [0, 0, 0], "height_ft": h, "source": "inferred_rectangle"},
    ]


def build_room_geometry(room: dict) -> dict:
    width_ft = room.get("width_ft")
    length_ft = room.get("length_ft")
    if not width_ft and not length_ft:
        # No real measurement for this room (e.g. an uploaded plan where the
        # printed dimension wasn't legible). Report that honestly instead of
        # fabricating a size - never invent a number that isn't in the source.
        source_plan = room.get("source_plan") or {}
        return {
            "coordinate_system": "room_local_ft",
            "source": "uploaded-plan-region" if source_plan.get("bbox_px") else "residence-a-authored-template",
            "source_fidelity": "dimensions_not_available_no_geometry_generated",
            "dimension_provenance": room.get("dimension_source", "not_available"),
            "width_ft": None,
            "depth_ft": None,
            "ceiling_ft": None,
            "boundary": None,
            "source_polygon_px": room.get("source_polygon_px"),
            "source_geometry": None,
            "walls": [],
            "doors": [],
            "windows": [],
            "connections": [x.get("to") for x in (room.get("links") or []) if x.get("to")],
        }

    w = float(width_ft or length_ft)
    d = float(length_ft or width_ft)
    h = float(room.get("ceiling_ft") or 11.0)

    source_geom = build_source_geometry(room)
    boundary = source_geom["boundary"] if source_geom else [[0, 0], [w, 0], [w, d], [0, d]]
    walls = source_geom["walls"] if source_geom else _rect_walls(w, d, h)

    links = room.get("links") or []
    doors = []
    if links:
        doors.append({
            "id": _opening_id("door", 1),
            "type": "entry_or_room_connection",
            "wall": "wall_north",
            "offset_ft": round(w / 2, 3),
            "width_ft": 3.0,
            "height_ft": 7.0,
            "inferred": True,
            "source_note": "opening inferred from room adjacency; exact location requires CAD/vector plan",
        })

    windows = []
    if room.get("view"):
        view_wall = room.get("view_wall", "south")
        span = w if view_wall in ("north", "south") else d
        windows.append({
            "id": _opening_id("window", 1),
            "type": "floor_to_ceiling_glass",
            "wall": f"wall_{view_wall}",
            "offset_ft": round(span / 2, 3),
            "width_ft": round(max(4.0, span * 0.8), 3),
            "sill_height_ft": 0.3,
            "head_height_ft": round(h - 0.6, 3),
            "inferred": True,
            "source_note": "glass wall inferred from visible exterior/view condition",
        })

    source_plan = room.get("source_plan") or {}
    source_mapped = bool(source_plan.get("bbox_px"))
    return {
        "coordinate_system": "room_local_ft",
        "source": "uploaded-plan-region" if source_mapped else "residence-a-authored-template",
        "source_fidelity": (
            "source_shape_plus_inferred_3d_openings" if source_mapped
            else "inferred_shell_not_exact_floorplan"
        ),
        "dimension_provenance": room.get("dimension_source", "template_or_unknown"),
        "width_ft": round(w, 3),
        "depth_ft": round(d, 3),
        "ceiling_ft": h,
        "boundary": boundary,
        "source_polygon_px": room.get("source_polygon_px"),
        "source_geometry": source_geom,
        "walls": walls,
        "doors": doors,
        "windows": windows,
        "connections": [x.get("to") for x in links if x.get("to")],
    }
