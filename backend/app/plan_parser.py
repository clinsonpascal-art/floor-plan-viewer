"""Generic uploaded floor-plan parser, for a unit that has no authored
template (i.e. any floor plan a viewer selects/uploads, not just Residence A
or the Continuum unit).

Room geometry (boundaries, walls, openings, and dimensions when a real scale
reference exists) comes ENTIRELY from the deterministic CV pipeline in
plan_detect.py - never from a vision/generative model, so it can never
hallucinate a room shape or a measurement.

Room NAME/TYPE (e.g. "this polygon is the kitchen") cannot be recovered from
geometry alone. When OPENAI_API_KEY is present, an optional vision-assist
step reads printed labels and maps them onto the ALREADY-DETECTED polygons
(it is only ever asked "what does the label near this exact box say", never
asked to draw a box itself). Without a key, rooms get an honest generic name
and an "unknown" room_type - never a guessed label.
"""
from __future__ import annotations

import base64
import json
import os
import re
from pathlib import Path

from .config import settings
from . import plan_detect, plan_upload_meta

_LABEL_PROMPT = """You are given an architectural floor plan image and a list of
already-detected room regions on that exact image, each with an index and its
exact pixel bounding box [x0,y0,x1,y1]. For each region, look ONLY at the
printed text inside or immediately touching that bounding box and report the
room name if one is legible there. Do not invent a name if none is printed or
legible in that region - use null. Do not add, remove, merge or move regions;
respond with exactly one entry per index, in the same order.
Regions: {regions}
Return strict JSON only: {"labels":[{"index":int,"name":string|null,"is_kitchen":bool,"is_bathroom":bool}]}"""

_TYPE_KEYWORDS = [
    ("kitchen", "kitchen"),
    ("bath", "bathroom"), ("wc", "bathroom"), ("powder", "bathroom"),
    ("primary", "bedroom"), ("master", "bedroom"), ("bed", "bedroom"),
    ("great", "living"), ("living", "living"), ("family", "living"),
    ("dining", "dining"),
    ("terrace", "outdoor"), ("patio", "outdoor"), ("balcony", "outdoor"), ("porch", "outdoor"),
    ("foyer", "foyer"), ("entry", "foyer"),
    ("corridor", "corridor"), ("hall", "corridor"), ("gallery", "corridor"),
    ("den", "den"), ("office", "den"), ("study", "den"),
    ("closet", "closet"), ("pantry", "closet"), ("laundry", "utility"), ("utility", "utility"),
    ("garage", "garage"),
]


def _mime(path: Path) -> str:
    return "image/png" if path.suffix.lower() == ".png" else "image/jpeg"


def _classify_room_type(name: str | None, label: dict) -> str:
    if label.get("is_kitchen"):
        return "kitchen"
    if label.get("is_bathroom"):
        return "bathroom"
    if not name:
        return "unknown"
    n = name.lower()
    for kw, room_type in _TYPE_KEYWORDS:
        if kw in n:
            return room_type
    return "unknown"


def _labels_from_vision(plan: Path, rooms: list) -> dict[int, dict]:
    """Optional refinement only: asks a vision model to read a printed label
    for each ALREADY-DETECTED polygon. Returns {} (never raises) if no key is
    configured or the call/parse fails - callers fall back to generic names."""
    if not os.getenv("OPENAI_API_KEY"):
        return {}
    try:
        from openai import OpenAI

        regions = []
        for idx, r in enumerate(rooms):
            xs = [p[0] for p in r.boundary_px]
            ys = [p[1] for p in r.boundary_px]
            regions.append({"index": idx, "bbox_px": [round(min(xs)), round(min(ys)), round(max(xs)), round(max(ys))]})

        b64 = base64.b64encode(plan.read_bytes()).decode()
        prompt = _LABEL_PROMPT.replace("{regions}", json.dumps(regions))
        client = OpenAI()
        response = client.chat.completions.create(
            model=settings.vision_model,
            messages=[{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:{_mime(plan)};base64,{b64}"}},
            ]}],
            temperature=0,
        )
        text = (response.choices[0].message.content or "").strip()
        text = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", text, flags=re.I)
        data = json.loads(text[text.find("{"):text.rfind("}") + 1])
        out: dict[int, dict] = {}
        for item in data.get("labels", []):
            idx = item.get("index")
            if isinstance(idx, int):
                out[idx] = item
        return out
    except Exception:
        return {}


def parse_uploaded_plan(plan: Path) -> list[dict]:
    """Detect room geometry deterministically from the uploaded image, then
    (only if a key is configured) optionally label the detected regions.
    Never invents a room boundary or a dimension."""
    total_interior_sqft = plan_upload_meta.read_total_interior_sqft(plan)
    detected = plan_detect.detect_plan(plan, total_interior_sqft=total_interior_sqft)
    if not detected.rooms:
        reason = "; ".join(detected.warnings) or "no rooms could be detected in this image"
        raise RuntimeError(f"The floor-plan analyzer could not detect any rooms ({reason}).")

    from PIL import Image
    with Image.open(plan) as im:
        iw, ih = im.size

    conn = plan_detect.infer_connections(detected.rooms, detected.openings)
    labels = _labels_from_vision(plan, detected.rooms)

    dim_source = {
        "manual_reference": "manual_reference",
        "dimension_text_ocr": "ocr_dimension_text",
        "total_area_anchor": "estimated_from_total_area_low_confidence",
    }.get(detected.scale.source if detected.scale else "", "not_available")

    ids: list[str] = []
    for idx, room in enumerate(detected.rooms):
        label = labels.get(idx) or {}
        name = (label.get("name") or "").strip() or f"Room {idx + 1}"
        rid = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or f"room_{idx + 1}"
        ids.append(rid)
    index_by_room_id = {room.id: idx for idx, room in enumerate(detected.rooms)}

    rooms = []
    for idx, room in enumerate(detected.rooms):
        label = labels.get(idx) or {}
        name = (label.get("name") or "").strip() or f"Room {idx + 1}"
        rid = ids[idx]
        room_type = _classify_room_type(label.get("name"), label)

        width_ft, length_ft = plan_detect.room_dimensions_ft(room, detected.scale)
        xs = [p[0] for p in room.boundary_px]
        ys = [p[1] for p in room.boundary_px]
        bbox_norm = [min(xs) / iw, min(ys) / ih, max(xs) / iw, max(ys) / ih]
        polygon_norm = [[x / iw, y / ih] for x, y in room.boundary_px]

        room_openings = plan_detect.openings_for_room(room, detected.openings)
        has_window = any(o.kind == "window" for o in room_openings)

        rooms.append({
            "id": rid,
            "name": name,
            "room_type": room_type,
            "width_ft": width_ft,
            "length_ft": length_ft,
            "bbox_norm": bbox_norm,
            "polygon_norm": polygon_norm,
            "view_wall": "detected" if has_window else None,
            "connections": [ids[index_by_room_id[other_id]] for other_id in conn.get(room.id, set())],
            "dimension_source": dim_source if (width_ft and length_ft) else "not_available",
        })
    return rooms
