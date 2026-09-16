"""
Structure-faithful control images — pure Python, no Blender, no GPU.

For each room we build a simple box shell from the plan dimensions (width, depth,
11' ceiling), place an eye-level wide-angle camera at the entry looking toward the
far wall, and render:
  - a DEPTH map   (near = bright)         -> depth-ControlNet
  - a LINEART map (wall/opening edges)    -> canny/scribble-ControlNet

Feeding this to a depth/edge-conditioned model makes the photoreal render obey the
room's real proportion, ceiling height and window-wall placement instead of the
model inventing a room. It constrains the SHELL; exact cabinetry still comes from
the prompt. Measurements are approximate by design (that was the call).
"""
import io
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

W_IMG, H_IMG = 1536, 1024
EYE_H = 5.2                 # camera height (ft)
CAM_SETBACK = 1.5          # camera sits this far outside the near wall (ft)
HFOV_DEG = 100.0           # wide real-estate lens
CEIL_FT = 11.0
_F = (W_IMG / 2) / math.tan(math.radians(HFOV_DEG) / 2)


def _dims(room: dict):
    w = room.get("width_ft") or room.get("length_ft") or 12.0
    d = room.get("length_ft") or room.get("width_ft") or 14.0
    return float(w), float(d), CEIL_FT


def _project(X, Y, Z, camX):
    zc = max(Z - (-CAM_SETBACK), 1e-3)
    sx = _F * (X - camX) / zc + W_IMG / 2
    sy = H_IMG / 2 - _F * (Y - EYE_H) / zc
    return sx, sy, 1.0 / zc


def _corners(W, D, H, camX):
    P = lambda x, y, z: _project(x, y, z, camX)
    return {
        "nbl": P(0, 0, 0), "nbr": P(W, 0, 0), "ntl": P(0, H, 0), "ntr": P(W, H, 0),
        "fbl": P(0, 0, D), "fbr": P(W, 0, D), "ftl": P(0, H, D), "ftr": P(W, H, D),
    }


def _faces(c):
    return [
        (c["nbl"], c["nbr"], c["fbr"], c["fbl"]),   # floor
        (c["ntl"], c["ntr"], c["ftr"], c["ftl"]),   # ceiling
        (c["nbl"], c["ntl"], c["ftl"], c["fbl"]),   # left wall
        (c["nbr"], c["ntr"], c["ftr"], c["fbr"]),   # right wall
        (c["fbl"], c["fbr"], c["ftr"], c["ftl"]),   # far wall
    ]


def _raster_depth(faces):
    """Z-buffer rasterize quads (2 tris each); output near=bright depth map."""
    zbuf = np.full((H_IMG, W_IMG), -1.0, dtype=np.float64)  # invz; larger=nearer
    ys, xs = np.mgrid[0:H_IMG, 0:W_IMG]
    for quad in faces:
        for tri in ((quad[0], quad[1], quad[2]), (quad[0], quad[2], quad[3])):
            (x0, y0, w0), (x1, y1, w1), (x2, y2, w2) = tri
            minx, maxx = max(int(min(x0, x1, x2)), 0), min(int(max(x0, x1, x2)) + 1, W_IMG)
            miny, maxy = max(int(min(y0, y1, y2)), 0), min(int(max(y0, y1, y2)) + 1, H_IMG)
            if minx >= maxx or miny >= maxy:
                continue
            det = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
            if abs(det) < 1e-6:
                continue
            sx, sy = xs[miny:maxy, minx:maxx], ys[miny:maxy, minx:maxx]
            a = ((y1 - y2) * (sx - x2) + (x2 - x1) * (sy - y2)) / det
            b = ((y2 - y0) * (sx - x2) + (x0 - x2) * (sy - y2)) / det
            g = 1 - a - b
            inside = (a >= 0) & (b >= 0) & (g >= 0)
            invz = a * w0 + b * w1 + g * w2
            reg = zbuf[miny:maxy, minx:maxx]
            upd = inside & (invz > reg)
            reg[upd] = invz[upd]
            zbuf[miny:maxy, minx:maxx] = reg
    valid = zbuf > -1.0
    out = np.zeros((H_IMG, W_IMG), dtype=np.uint8)
    if valid.any():
        v = zbuf[valid]
        lo, hi = v.min(), v.max()
        norm = (zbuf - lo) / (hi - lo + 1e-9)
        out[valid] = np.clip(norm[valid] * 255, 0, 255).astype(np.uint8)
    return Image.fromarray(out, mode="L")


def _lineart(c, W, D, H, camX, view, has_side_door, room_geometry=None):
    img = Image.new("L", (W_IMG, H_IMG), 255)
    d = ImageDraw.Draw(img)
    xy = lambda p: (p[0], p[1])
    edges = [("nbl","nbr"),("nbr","ntr"),("ntr","ntl"),("ntl","nbl"),
             ("fbl","fbr"),("fbr","ftr"),("ftr","ftl"),("ftl","fbl"),
             ("nbl","fbl"),("nbr","fbr"),("ntl","ftl"),("ntr","ftr")]
    for a, b in edges:
        d.line([xy(c[a]), xy(c[b])], fill=0, width=3)
    P = lambda x, y, z: _project(x, y, z, camX)[:2]
    geom = room_geometry or {}
    windows = geom.get("windows") or []
    doors = geom.get("doors") or []
    if windows:
        for win_meta in windows:
            wall = win_meta.get("wall")
            ww = float(win_meta.get("width_ft", W * 0.8))
            if wall in ("wall_north", "wall_south"):
                cx = float(win_meta.get("offset_ft", W / 2))
                x0, x1 = max(0.05, cx - ww / 2), min(W - 0.05, cx + ww / 2)
                y = 0 if wall == "wall_north" else D
                win = [P(x0, 0.3, y), P(x1, 0.3, y), P(x1, H-0.6, y), P(x0, H-0.6, y)]
                d.polygon(win, outline=0, width=3)
                for i in range(1, 5):
                    x = x0 + (x1 - x0) * i / 5
                    d.line([P(x, 0.3, y), P(x, H-0.6, y)], fill=0, width=2)
            elif wall in ("wall_east", "wall_west"):
                cy = float(win_meta.get("offset_ft", D / 2))
                y0, y1 = max(0.05, cy - ww / 2), min(D - 0.05, cy + ww / 2)
                x = W if wall == "wall_east" else 0
                win = [P(x, y0, 0.3), P(x, y1, 0.3), P(x, y1, H-0.6), P(x, y0, H-0.6)]
                d.polygon(win, outline=0, width=3)
                for i in range(1, 5):
                    yv = y0 + (y1 - y0) * i / 5
                    d.line([P(x, yv, 0.3), P(x, yv, H-0.6)], fill=0, width=2)
    elif view:
        win = [P(W*0.10, 0.3, D), P(W*0.90, 0.3, D), P(W*0.90, H-0.6, D), P(W*0.10, H-0.6, D)]
        d.polygon(win, outline=0, width=3)
    if doors:
        # Current inferred door model is on the near/north wall. Exact openings
        # will be replaced when floor-plan coordinates are available.
        for door_meta in doors:
            if door_meta.get("wall") == "wall_north":
                dw = float(door_meta.get("width_ft", 3.0))
                cx = float(door_meta.get("offset_ft", W / 2))
                x0, x1 = max(0.05, cx - dw / 2), min(W - 0.05, cx + dw / 2)
                door = [P(x0, 0, 0), P(x0, 0, float(door_meta.get("height_ft", 7.0))),
                        P(x1, 0, float(door_meta.get("height_ft", 7.0))), P(x1, 0, 0)]
                d.polygon(door, outline=0, width=3)
    elif has_side_door:
        door = [P(W, 0, 1.2), P(W, 0, 4.2), P(W, 6.8, 4.2), P(W, 6.8, 1.2)]
        d.polygon(door, outline=0, width=3)
    return img


def control_for_room(room: dict, mode: str = "depth") -> bytes | None:
    """Return PNG bytes of the control image for `room`, or None if mode == 'none'."""
    mode = (mode or "depth").lower()
    if mode == "none":
        return None
    W, D, H = _dims(room)
    camX = W / 2
    c = _corners(W, D, H, camX)
    view = bool(room.get("view"))
    has_side_door = bool(room.get("links"))
    if mode in ("canny", "lineart"):
        try:
            from .room_geometry import build_room_geometry
            room_geom = build_room_geometry(room)
        except Exception:
            room_geom = None
        img = _lineart(c, W, D, H, camX, view, has_side_door, room_geom)
    else:
        img = _raster_depth(_faces(c))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def plan_edges(plan: Path | None) -> bytes | None:
    """Fallback: whole-plan edge map."""
    if not plan:
        return None
    try:
        from PIL import ImageFilter, ImageOps
        img = ImageOps.grayscale(Image.open(plan)).filter(ImageFilter.FIND_EDGES)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return None


if __name__ == "__main__":  # python -m app.geometry [outdir]
    import sys
    from .analyze import TEMPLATE_RESIDENCE_A
    outdir = Path(sys.argv[1] if len(sys.argv) > 1 else "./control_preview")
    outdir.mkdir(parents=True, exist_ok=True)
    for rid, room in TEMPLATE_RESIDENCE_A.items():
        for mode in ("depth", "canny"):
            b = control_for_room({**room, "id": rid}, mode)
            if b:
                (outdir / f"{rid}.{mode}.png").write_bytes(b)
    print(f"wrote control previews to {outdir}/")
