"""Create reviewable room-specific crops from the uploaded floor-plan sheet."""
from __future__ import annotations

import io
from pathlib import Path
from PIL import Image, ImageDraw, ImageEnhance


def room_plan_crop(plan: Path | None, room: dict) -> bytes | None:
    if not plan or not room.get("source_plan", {}).get("bbox_px"):
        return None
    try:
        img = Image.open(plan).convert("RGB")
        x0, y0, x1, y1 = room["source_plan"]["bbox_px"]
        pad = 18
        x0, y0 = max(0, x0-pad), max(0, y0-pad)
        x1, y1 = min(img.width, x1+pad), min(img.height, y1+pad)
        crop = img.crop((x0, y0, x1, y1))
        crop = ImageEnhance.Contrast(crop).enhance(1.12)
        d = ImageDraw.Draw(crop)
        d.rectangle((pad, pad, crop.width-pad-1, crop.height-pad-1), outline=(210, 35, 35), width=4)
        label = room.get("source_plan", {}).get("label") or room.get("name", "ROOM")
        d.rectangle((0, 0, min(crop.width, 330), 28), fill=(255,255,255))
        d.text((8, 7), f"SOURCE REGION: {label}", fill=(160, 20, 20))
        buf = io.BytesIO()
        crop.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return None
