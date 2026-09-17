from pathlib import Path
import json
import shutil

from app.pipeline import generate_unit

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "source_continuum_residence_01.jpg"


def test_continuum_source_grounded():
    out = ROOT / "renders_continuum_smoke"
    shutil.rmtree(out, ignore_errors=True)  # avoid stale artifacts from a previous run
    import app.config as cfg
    old = cfg.settings.out_dir
    cfg.settings.out_dir = str(out)
    try:
        manifest = generate_unit("continuum-residence-01", PLAN, provider="mock")
        assert len(manifest["order"]) == 10
        assert manifest["source_plan"]["summary"]["interior_sf"] == 2080
        for rid in manifest["order"]:
            room = manifest["rooms"][rid]
            assert room["source_plan"]["bbox_px"]
            assert room["geometry"]["source_polygon_px"]
            assert (out / "continuum-residence-01" / f"{rid}.jpg").exists()
            control_path = out / "continuum-residence-01" / f"{rid}.control.png"
            has_measured_dims = room["geometry"]["width_ft"] is not None
            if has_measured_dims:
                assert control_path.exists(), f"{rid}: expected a control image for a room with a known dimension"
            else:
                # e.g. the terrace, which continuum_template.py deliberately
                # leaves unmeasured rather than assign a fake footprint - no
                # control image should be fabricated from an invented size.
                assert not control_path.exists(), f"{rid}: no real dimension was available, so no control image should exist"
    finally:
        cfg.settings.out_dir = old
