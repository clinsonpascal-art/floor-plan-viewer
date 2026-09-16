"""Generic uploaded floor-plan parser.

For known source-grounded units the existing templates remain authoritative.
For a new floor plan, an OpenAI vision model can return a small room graph with
normalized source regions. The parser never invents printed dimensions: missing
dimensions remain null.
"""
from __future__ import annotations

import base64
import json
import os
import re
from pathlib import Path

from .config import settings

PROMPT = """Analyze this architectural floor plan only. Return strict JSON with this shape:
{"rooms":[{"id":"stable_slug","name":"Printed Room Name","width_ft":number|null,"length_ft":number|null,"bbox":[x0,y0,x1,y1],"polygon":[[x,y],...],"view_wall":"north|south|east|west|null","connections":["other_stable_slug"]}]}
Rules:
- Include every distinct labeled interior room and terrace/outdoor area that is visibly part of the selected residence.
- Use a stable lowercase snake_case id derived from the printed room name.
- Copy dimensions only when printed and legible. Otherwise use null; never estimate dimensions.
- bbox and polygon coordinates are normalized 0..1 relative to the uploaded image.
- Use a polygon only when the room boundary is visually clear; otherwise return an empty list.
- connections should reflect visible door/opening adjacency only when clear.
- Do not invent rooms hidden outside the residence or information not visible in the image."""


def _mime(path: Path) -> str:
    return "image/png" if path.suffix.lower() == ".png" else "image/jpeg"


def parse_uploaded_plan(plan: Path) -> list[dict]:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("An OPENAI_API_KEY is required to analyze an unregistered floor plan.")
    from openai import OpenAI

    b64 = base64.b64encode(plan.read_bytes()).decode()
    client = OpenAI()
    response = client.chat.completions.create(
        model=settings.vision_model,
        messages=[{"role": "user", "content": [
            {"type": "text", "text": PROMPT},
            {"type": "image_url", "image_url": {"url": f"data:{_mime(plan)};base64,{b64}"}},
        ]}],
        temperature=0,
    )
    text = (response.choices[0].message.content or "").strip()
    text = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", text, flags=re.I)
    data = json.loads(text[text.find("{"):text.rfind("}") + 1])
    rooms = []
    for item in data.get("rooms", []):
        name = str(item.get("name") or "Room").strip()
        rid = re.sub(r"[^a-z0-9]+", "_", str(item.get("id") or name).lower()).strip("_") or "room"
        bbox = item.get("bbox") or []
        polygon = item.get("polygon") or []
        if len(bbox) != 4:
            bbox = []
        if polygon and not all(isinstance(p, list) and len(p) == 2 for p in polygon):
            polygon = []
        rooms.append({
            "id": rid,
            "name": name,
            "width_ft": item.get("width_ft"),
            "length_ft": item.get("length_ft"),
            "bbox_norm": bbox,
            "polygon_norm": polygon,
            "view_wall": item.get("view_wall"),
            "connections": item.get("connections") or [],
            "dimension_source": "printed_on_uploaded_plan" if item.get("width_ft") and item.get("length_ft") else "not_available",
        })
    if not rooms:
        raise RuntimeError("The floor-plan analyzer did not identify any rooms.")
    return rooms
