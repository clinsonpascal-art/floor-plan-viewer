from pathlib import Path
import json

from app.pipeline import generate_unit

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "source_continuum_residence_01.jpg"


def test_continuum_source_grounded():
    out = ROOT / "renders_continuum_smoke"
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
            assert (out / "continuum-residence-01" / f"{rid}.control.png").exists()
    finally:
        cfg.settings.out_dir = old
