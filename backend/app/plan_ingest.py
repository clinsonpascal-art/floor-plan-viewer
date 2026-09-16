"""Attach grounded source-plan information to analyzed rooms.

This is a reconstruction aid for the supplied Continuum Residence 01 screenshot.
It does not claim pixel annotations are CAD-accurate.
"""
from __future__ import annotations
from pathlib import Path

from .continuum_plan import PLAN_SIZE, RESIDENCE_01_SOURCE_ROOMS, RESIDENCE_01_TERRACES, SOURCE_SUMMARY


def source_info(unit_id: str, plan: Path | None) -> dict | None:
    if unit_id not in ("residence-a", "continuum-residence-01") or not plan:
        return None
    return {
        "type": "uploaded_floor_plan_screenshot",
        "file": plan.name,
        "plan_size_px": PLAN_SIZE,
        "summary": SOURCE_SUMMARY,
        "rooms": RESIDENCE_01_SOURCE_ROOMS,
        "terraces": RESIDENCE_01_TERRACES,
        "fidelity": "annotated_visible_plan_regions_not_CAD",
    }


def attach_room_source(room: dict, source: dict | None) -> dict:
    if not source:
        return room
    rid = room.get("id")
    item = source.get("rooms", {}).get(rid) or source.get("terraces", {}).get(rid)
    if rid == "terrace" and not item:
        item = {"source_label": "TERRACES A/B/C", "bbox_px": [220, 95, 800, 275]}
    if item:
        room["source_plan"] = {
            "label": item["source_label"],
            "bbox_px": item["bbox_px"],
            "polygon_px": item.get("polygon_px"),
            "plan_size_px": source["plan_size_px"],
            "fidelity": source["fidelity"],
            "region_type": "terrace" if rid.startswith("terrace") else "interior_room",
        }
    else:
        room["source_plan"] = {
            "label": None,
            "bbox_px": None,
            "plan_size_px": source["plan_size_px"],
            "fidelity": "not_mapped_to_uploaded_plan",
        }
    return room
