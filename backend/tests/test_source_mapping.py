from pathlib import Path

from app.plan_ingest import source_info


def test_continuum_source_mapping():
    plan = Path(__file__).resolve().parents[1] / "source_continuum_residence_01.jpg"
    src = source_info("continuum-residence-01", plan)
    assert src is not None
    assert src["summary"]["interior_sf"] == 2080
    assert src["rooms"]["great"]["source_label"] == "LIVING ROOM"
    assert src["rooms"]["primary"]["source_label"] == "PRIMARY BEDROOM"
