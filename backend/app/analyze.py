"""Turn a floor plan into the room list the pipeline + tour need.

The LAYOUT GRAPH (positions, adjacency/doorways, minimap rects) is authored per
unit as a template — it can't be auto-derived to tour quality. Vision only
refines room presence + dimensions. Add a new unit by adding a TEMPLATE entry.
"""
import base64
import json
import os
import re
from pathlib import Path

from .plan_ingest import source_info, attach_room_source
from .continuum_template import build_template
from .plan_parser import parse_uploaded_plan

# Residence A — 1428 Brickell. Same shape the tour engine expects.
TEMPLATE_RESIDENCE_A = {
    "foyer":    {"name": "Private Foyer", "dim": "20′ × 6′", "width_ft": 20, "length_ft": 6,
                 "view": False, "backDoor": True, "feat": "Double-door entry · private elevator vestibule",
                 "x": 96, "y": 20, "w": 34, "h": 22,
                 "links": [{"to": "corridor", "label": "Corridor", "px": 50, "py": 80, "chev": "↓"}]},
    "corridor": {"name": "Corridor", "dim": "Gallery hall", "width_ft": None, "length_ft": None,
                 "view": False, "backDoor": True, "feat": "Connects foyer, den, great room and the primary wing",
                 "x": 60, "y": 44, "w": 24, "h": 40,
                 "links": [{"to": "foyer", "label": "Foyer", "px": 80, "py": 24, "chev": "↑"},
                           {"to": "den", "label": "Den", "px": 16, "py": 44, "chev": "←"},
                           {"to": "great", "label": "Great Room", "px": 52, "py": 84, "chev": "↓"},
                           {"to": "primary", "label": "Primary", "px": 18, "py": 80, "chev": "↙"}]},
    "den":      {"name": "Den", "dim": "12′6″ × 8′4″", "width_ft": 12.5, "length_ft": 8.33,
                 "view": False, "backDoor": False, "feat": "Flex study / media · en-suite Bath 3 adjacent",
                 "x": 16, "y": 20, "w": 34, "h": 22,
                 "links": [{"to": "corridor", "label": "Corridor", "px": 82, "py": 60, "chev": "→"}]},
    "great":    {"name": "Great Room", "dim": "18′ × 15′4″", "width_ft": 18, "length_ft": 15.33,
                 "view": True, "feat": "East floor-to-ceiling glass · opens to the Sunrise Terrace",
                 "x": 46, "y": 88, "w": 46, "h": 44,
                 "links": [{"to": "corridor", "label": "Corridor", "px": 50, "py": 16, "chev": "↑"},
                           {"to": "kitchen", "label": "Kitchen", "px": 88, "py": 42, "chev": "→"},
                           {"to": "bed2", "label": "Bedroom 2", "px": 90, "py": 72, "chev": "↘"},
                           {"to": "terrace", "label": "Terrace", "px": 50, "py": 90, "chev": "↓"}]},
    "kitchen":  {"name": "Kitchen", "dim": "15′4″ × 13′6″", "width_ft": 15.33, "length_ft": 13.5,
                 "view": False, "backDoor": False,
                 "feat": "Center island · Gaggenau cooktop, double oven, fridge/freezer · wine cooler · pantry",
                 "x": 96, "y": 64, "w": 34, "h": 30,
                 "links": [{"to": "great", "label": "Great Room", "px": 14, "py": 52, "chev": "←"}]},
    "primary":  {"name": "Primary Bedroom", "dim": "15′8″ × 12′3″", "width_ft": 15.67, "length_ft": 12.25,
                 "view": True, "feat": "East / bay view · en-suite Primary Bath · walk-in closet",
                 "x": 10, "y": 104, "w": 34, "h": 34,
                 "links": [{"to": "corridor", "label": "Corridor", "px": 80, "py": 16, "chev": "↗"},
                           {"to": "pbath", "label": "Primary Bath", "px": 16, "py": 52, "chev": "←"}]},
    "pbath":    {"name": "Primary Bath", "dim": "14′ × 12′4″", "width_ft": 14, "length_ft": 12.33,
                 "view": False, "backDoor": False,
                 "feat": "Freestanding tub · dual vanity · Arclinea detailing · high-efficiency WC",
                 "x": 10, "y": 62, "w": 34, "h": 34,
                 "links": [{"to": "primary", "label": "Primary Bedroom", "px": 56, "py": 86, "chev": "↓"}]},
    "bed2":     {"name": "Bedroom 2", "dim": "15′7″ × 11′", "width_ft": 15.58, "length_ft": 11,
                 "view": True, "feat": "East / bay view · en-suite Bath 2 · walk-in closet",
                 "x": 96, "y": 104, "w": 34, "h": 34,
                 "links": [{"to": "great", "label": "Great Room", "px": 14, "py": 36, "chev": "←"}]},
    "terrace":  {"name": "Sunrise Terrace", "dim": "40′ × 12′3″", "width_ft": 40, "length_ft": 12.25,
                 "view": True, "feat": "Wraparound east terrace · summer kitchen · glass rail over Biscayne Bay",
                 "x": 40, "y": 140, "w": 70, "h": 16,
                 "links": [{"to": "great", "label": "Great Room", "px": 50, "py": 14, "chev": "↑"}]},
}
UNIT_TEMPLATES = {"residence-a": TEMPLATE_RESIDENCE_A, "continuum-residence-01": build_template()}

_VISION_PROMPT = """Analyze only the visible architectural floor plan. Return JSON:
{"rooms":[{"id":string,"width_ft":number|null,"length_ft":number|null}]}
Use these ids where present: great, kitchen, primary, pbath, bed2, bed3, bath2, bath3, powder, terrace. Copy dimensions only when printed and legible. Never invent."""


def _dims_from_vision(plan: Path, provider: str) -> dict:
    """Optional refinement. Only runs for the openai provider with a key present."""
    if provider != "openai" or not os.getenv("OPENAI_API_KEY") or not plan:
        return {}
    try:
        from openai import OpenAI
        from .config import settings
        mime = "image/png" if plan.suffix.lower() == ".png" else "image/jpeg"
        b64 = base64.b64encode(plan.read_bytes()).decode()
        r = OpenAI().chat.completions.create(
            model=settings.vision_model,
            messages=[{"role": "user", "content": [
                {"type": "text", "text": _VISION_PROMPT},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}]}])
        txt = re.sub(r"^\s*```(?:json)?|```\s*$", "", r.choices[0].message.content.strip(), flags=re.I)
        data = json.loads(txt[txt.find("{"):txt.rfind("}") + 1])
        return {d["id"]: d for d in data.get("rooms", []) if d.get("id")}
    except Exception:
        return {}  # fall back to template dims


def get_rooms(unit_id: str, plan: Path | None, provider: str, only: list | None = None):
    # Known units use their source-grounded layout graph. Unknown units are
    # parsed from the uploaded floor plan instead of silently falling back to
    # Residence A.
    if unit_id in UNIT_TEMPLATES:
        template = UNIT_TEMPLATES[unit_id]
        overrides = _dims_from_vision(plan, provider) if plan else {}
        source = source_info(unit_id, plan)
        rooms = []
        for rid, base in template.items():
            if only and rid not in only:
                continue
            r = dict(base)
            r["id"] = rid
            ov = overrides.get(rid, {})
            if ov.get("width_ft"):
                r["width_ft"] = ov["width_ft"]
            if ov.get("length_ft"):
                r["length_ft"] = ov["length_ft"]
            attach_room_source(r, source)
            rooms.append(r)
        return rooms

    if not plan:
        raise ValueError("An uploaded floor plan is required for a new unit.")
    parsed = parse_uploaded_plan(plan)
    from PIL import Image
    with Image.open(plan) as im:
        iw, ih = im.size
    rooms = []
    by_name = {}
    seen_ids: dict[str, int] = {}
    for item in parsed:
        base_rid = item["id"]
        seen_ids[base_rid] = seen_ids.get(base_rid, 0) + 1
        # Two distinct rooms can slugify to the same id (e.g. two ambiguously
        # named/unlabeled regions both falling back to "room", or two rooms
        # sharing a printed name). Without disambiguation, every downstream
        # write (image file, control image, manifest node) is keyed by rid,
        # so a collision silently overwrites the first room's render/data
        # with the second's - both rooms end up pointing at the same asset.
        rid = base_rid if seen_ids[base_rid] == 1 else f"{base_rid}_{seen_ids[base_rid]}"
        if only and rid not in only:
            continue
        bbox = item.get("bbox_norm") or []
        if len(bbox) == 4:
            bbox_px = [round(max(0, min(iw, bbox[0]*iw))), round(max(0, min(ih, bbox[1]*ih))),
                       round(max(0, min(iw, bbox[2]*iw))), round(max(0, min(ih, bbox[3]*ih)))]
        else:
            bbox_px = None
        polygon = []
        for x, y in item.get("polygon_norm") or []:
            polygon.append([round(max(0, min(iw, x*iw))), round(max(0, min(ih, y*ih)))])
        r = {
            "id": rid, "name": item["name"], "room_type": item.get("room_type", "unknown"),
            "width_ft": item.get("width_ft"), "length_ft": item.get("length_ft"),
            "dim": (f"{item['width_ft']:g}′ × {item['length_ft']:g}′" if item.get("width_ft") and item.get("length_ft") else "Dimension not available"),
            "dimension_source": item.get("dimension_source", "not_available"),
            "view": bool(item.get("view_wall")), "view_wall": item.get("view_wall"),
            "feat": "Parsed from uploaded floor plan", "x": 0, "y": 0, "w": 0, "h": 0,
            "links": [{"to": c} for c in item.get("connections", []) if c],
            "source_polygon_px": polygon or ([
                [bbox_px[0], bbox_px[1]], [bbox_px[2], bbox_px[1]],
                [bbox_px[2], bbox_px[3]], [bbox_px[0], bbox_px[3]]
            ] if bbox_px else []),
        }
        if bbox_px:
            r["source_plan"] = {"label": item["name"], "bbox_px": bbox_px, "polygon_px": polygon or None,
                                "plan_size_px": [iw, ih], "fidelity": "vision_parsed_uploaded_plan",
                                "region_type": "interior_room"}
        rooms.append(r)
        by_name[rid] = r
    if not rooms:
        raise ValueError("No rooms matched the requested selection.")
    return rooms
