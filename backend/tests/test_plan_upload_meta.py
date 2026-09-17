"""Unit tests for the total_interior_sqft sidecar (Option 1 scale reference).
No API/network involved - just the read/write round trip and the
"never write a fabricated value" / "never collide with the plan file itself"
guarantees main.py and plan_parser.py depend on.
"""
from pathlib import Path

from app import plan_upload_meta


def test_write_then_read_round_trip(tmp_path):
    plan = tmp_path / "abc123.jpg"
    plan.write_bytes(b"not a real image, just a placeholder for the path")

    plan_upload_meta.write_plan_meta(plan, 2080.0)

    assert plan_upload_meta.read_total_interior_sqft(plan) == 2080.0


def test_no_sidecar_returns_none_not_a_guess(tmp_path):
    plan = tmp_path / "no_meta_here.jpg"
    plan.write_bytes(b"placeholder")

    assert plan_upload_meta.read_total_interior_sqft(plan) is None


def test_write_with_none_is_a_no_op(tmp_path):
    plan = tmp_path / "xyz.jpg"
    plan.write_bytes(b"placeholder")

    plan_upload_meta.write_plan_meta(plan, None)

    assert not plan_upload_meta.meta_path(plan).exists()
    assert plan_upload_meta.read_total_interior_sqft(plan) is None


def test_sidecar_path_never_collides_with_the_glob_used_to_find_the_plan(tmp_path):
    """main.py's _resolve_plan() finds an uploaded plan via
    glob(f"{input_id}.*") - the sidecar's filename must never match that
    pattern, or it could get returned as "the plan" instead of the image."""
    plan = tmp_path / "d34db33f.jpg"
    plan.write_bytes(b"placeholder")
    plan_upload_meta.write_plan_meta(plan, 1500.0)

    matches = list(tmp_path.glob("d34db33f.*"))
    assert matches == [plan]
