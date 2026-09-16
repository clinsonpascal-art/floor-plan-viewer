"""Deterministic pre-publish checks for generated LUXE room packages.

This validates the pipeline artifacts and room graph without pretending that
computer vision has proved a generated image matches the source floor plan.
The visual match remains a review step until a real vision comparator is wired in.
"""
from pathlib import Path


def validate_manifest(manifest: dict, out_dir: Path) -> dict:
    rooms = manifest.get("rooms", {})
    order = manifest.get("order", [])
    errors: list[str] = []
    warnings: list[str] = []

    # Source-plan annotations are intentionally checked separately from render
    # validity. A room without a mapping is a reconstruction gap, not an error.

    if not rooms:
        errors.append("manifest contains no rooms")
    if set(order) != set(rooms):
        errors.append("order and rooms keys do not match")

    for rid in order:
        room = rooms.get(rid, {})
        if not room:
            errors.append(f"missing room node: {rid}")
            continue
        for key in ("name", "dim", "panorama_url"):
            if not room.get(key):
                errors.append(f"{rid}: missing {key}")
        geom = room.get("geometry") or {}
        if not geom.get("boundary"):
            warnings.append(f"{rid}: room geometry boundary missing")
        if geom.get("source_fidelity") != "exact_floorplan":
            if room.get("source_plan", {}).get("bbox_px"):
                warnings.append(f"{rid}: 3D shell geometry is still inferred; source-plan region is mapped")
            else:
                warnings.append(f"{rid}: geometry is inferred until source floor plan is parsed")
        for link in room.get("links", []):
            target = link.get("to")
            if target not in rooms:
                errors.append(f"{rid}: link points to unknown room {target!r}")

        render = out_dir / f"{rid}.jpg"
        control = out_dir / f"{rid}.control.png"
        plan_crop = out_dir / f"{rid}.plan.png"
        if not render.exists():
            errors.append(f"{rid}: render missing ({render.name})")
        if not control.exists():
            warnings.append(f"{rid}: control image missing ({control.name})")
        if room.get("source_plan", {}).get("bbox_px") and not plan_crop.exists():
            warnings.append(f"{rid}: source-plan crop missing ({plan_crop.name})")

    unmapped = [rid for rid in order if not rooms.get(rid, {}).get("source_plan", {}).get("bbox_px")]
    if unmapped:
        warnings.append("source plan has no mapped region for: " + ", ".join(unmapped))

    status = "pass" if not errors else "fail"
    return {
        "status": status,
        "errors": errors,
        "warnings": warnings,
        "visual_floorplan_match": "manual_review_required",
    }
