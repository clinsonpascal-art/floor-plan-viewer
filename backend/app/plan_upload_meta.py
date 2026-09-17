"""Sidecar metadata for an uploaded floor-plan file.

Currently just an optional caller-supplied total interior square footage,
used as a fallback scale reference (see plan_scale.calibrate_from_total_area)
when no printed dimension text can be read from the image itself. Stored as
"{plan_stem}.meta.json" next to the uploaded image - main.py writes it at
upload/job-creation time, plan_parser.py reads it before analysis. This is
upload-time metadata, not job state, so it is never persisted in jobs.py.
"""
from __future__ import annotations

import json
from pathlib import Path


def meta_path(plan: Path) -> Path:
    # "meta_" prefix (not a modified suffix) is deliberate: main.py's
    # _resolve_plan() finds the uploaded plan via glob("{input_id}.*"), which
    # would also match a same-stem sidecar like "{input_id}.meta.json" and
    # could get returned as "the plan" instead of the real image.
    return plan.parent / f"meta_{plan.stem}.json"


def write_plan_meta(plan: Path, total_interior_sqft: float | None) -> None:
    """No-op when nothing is supplied - never writes a fabricated value."""
    if not total_interior_sqft:
        return
    meta_path(plan).write_text(
        json.dumps({"total_interior_sqft": total_interior_sqft}), encoding="utf-8"
    )


def read_total_interior_sqft(plan: Path) -> float | None:
    """Returns None (not a guess) whenever no sidecar exists or it's unreadable."""
    p = meta_path(plan)
    if not p.exists():
        return None
    try:
        value = json.loads(p.read_text(encoding="utf-8")).get("total_interior_sqft")
        return float(value) if value else None
    except Exception:
        return None
