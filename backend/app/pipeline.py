"""Orchestration: floor plan -> photoreal rooms -> files the tour reads."""
import json
from pathlib import Path

from . import analyze, geometry, prompts
from .room_geometry import build_room_geometry
from .config import settings, resolve_provider
from .providers import get_provider
from .validation import validate_manifest
from .plan_ingest import source_info
from .plan_crop import room_plan_crop
from .static_room_images import STATIC_ROOM_IMAGES

STATIC_DIR = Path(__file__).resolve().parents[1] / "static"

DISCLAIMER = ("AI architectural visualization generated from the developer floor plan. "
              "Furnishings illustrative; dimensions approximate and subject to change.")


def generate_unit(unit_id: str, plan: Path | None = None, staged: bool = False,
                  only: list | None = None, provider: str | None = None) -> dict:
    prov_name = provider or resolve_provider()
    prov = get_provider(prov_name)
    rooms = analyze.get_rooms(unit_id, plan, prov_name, only)

    out = Path(settings.out_dir) / unit_id
    out.mkdir(parents=True, exist_ok=True)

    graph, order, panos = {}, [], {}
    for r in rooms:
        rid = r["id"]
        prompt = prompts.build_prompt(rid, r["name"], r.get("width_ft"), r.get("length_ft"),
                                      view=r.get("view", False), staged=staged, room_type=r.get("room_type"))
        control = geometry.control_for_room(r, settings.control_mode)
        if control:
            (out / f"{rid}.control.png").write_bytes(control)   # structural control / debugging
        plan_crop = room_plan_crop(plan, r)
        if plan_crop:
            (out / f"{rid}.plan.png").write_bytes(plan_crop)   # source-grounding evidence
        static_rel = STATIC_ROOM_IMAGES.get(unit_id, {}).get(rid)
        if static_rel:
            img = (STATIC_DIR / static_rel).read_bytes()   # real photo override, no generation
        else:
            img = prov.generate(prompt, settings.image_size, control)
        (out / f"{rid}.jpg").write_bytes(img)

        url = f"{settings.public_base}/{unit_id}/{rid}.jpg"
        panos[rid] = url
        node = {k: r[k] for k in ("name", "dim", "view", "feat", "x", "y", "w", "h", "links", "source_plan",
                                  "room_type", "dimension_source") if k in r}
        node["geometry"] = build_room_geometry(r)
        if plan_crop:
            node["source_plan_crop_url"] = f"{settings.public_base}/{unit_id}/{rid}.plan.png"
        node["panorama_url"] = url
        # Multiple viewpoints per room, smallest-possible extension of the
        # existing single-panorama_url shape: today there is exactly one real
        # generated/static image per room, so this is a length-1 list built
        # from that same real url - never a second, invented image. A future
        # generation pass that produces more angles for a room only needs to
        # append more entries here; nothing downstream has to change shape.
        node["viewpoints"] = [{"id": "main", "label": "Main View", "url": url}]
        graph[rid] = node
        order.append(rid)

    # Files the tour consumes directly (data-driven, multi-unit).
    (out / "rooms.js").write_text(
        "window.LUXE_ROOMS = " + json.dumps(graph, ensure_ascii=False, indent=2) + ";\n"
        "window.LUXE_ORDER = " + json.dumps(order) + ";\n", encoding="utf-8")
    (out / "panoramas.js").write_text(
        "window.LUXE_PANOS = " + json.dumps(panos, ensure_ascii=False, indent=2) + ";\n", encoding="utf-8")
    manifest = {"unit": unit_id, "status": "review_required", "provider": prov_name,
                "disclaimer": DISCLAIMER, "order": order, "rooms": graph}
    src = source_info(unit_id, plan)
    if src:
        manifest["source_plan"] = {"type": src["type"], "file": src["file"],
                                   "plan_size_px": src["plan_size_px"],
                                   "summary": src["summary"],
                                   "fidelity": src["fidelity"]}
    manifest["validation"] = validate_manifest(manifest, out)
    (out / "validation.json").write_text(json.dumps(manifest["validation"], ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":                       # offline CLI: python -m app.pipeline ...
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--unit", default="residence-a")
    ap.add_argument("--plan", type=Path)
    ap.add_argument("--staged", action="store_true")
    ap.add_argument("--only")
    ap.add_argument("--provider")
    a = ap.parse_args()
    only = [s.strip() for s in a.only.split(",")] if a.only else None
    m = generate_unit(a.unit, a.plan, a.staged, only, a.provider)
    print(json.dumps({"unit": m["unit"], "status": m["status"],
                      "rooms": list(m["rooms"])}, indent=2))
