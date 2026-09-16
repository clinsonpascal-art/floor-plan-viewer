"""Phase 1 accuracy test: scale calibration.

Method 1 (manual reference) and Method 3 (total-area anchor) are pure
arithmetic and graded exactly. Method 2 (OCR dimension text) is exercised
only if pytesseract is installed (it's an optional assist, not a hard
dependency of the pipeline) and is skipped otherwise.
"""
import math

import pytest

from app import plan_scale
from app.plan_geom_types import WallSegment


def test_manual_reference_calibration_is_exact():
    cal = plan_scale.calibrate_from_reference((0.0, 0.0), (100.0, 0.0), known_ft=10.0)
    assert cal.source == "manual_reference"
    assert cal.confidence == 1.0
    assert math.isclose(cal.px_per_ft, 10.0)


def test_known_px_per_ft_passthrough():
    cal = plan_scale.calibrate_from_known_px_per_ft(12.5)
    assert cal.px_per_ft == 12.5
    assert cal.source == "manual_reference"


def test_total_area_anchor_calibration():
    # 2080 sqft interior spread over a 1000x1000 px region -> px_per_ft = sqrt(1e6/2080)
    cal = plan_scale.calibrate_from_total_area(total_sqft=2080.0, detected_area_px2=1_000_000.0)
    expected = math.sqrt(1_000_000.0 / 2080.0)
    assert math.isclose(cal.px_per_ft, expected, rel_tol=1e-9)
    assert cal.source == "total_area_anchor"
    assert cal.confidence == 0.4


def test_total_area_anchor_rejects_nonpositive_inputs():
    with pytest.raises(ValueError):
        plan_scale.calibrate_from_total_area(total_sqft=0.0, detected_area_px2=100.0)


def test_parse_dimension_text():
    assert plan_scale._parse_dimension_text("12'-6\"") == pytest.approx(12.5)
    assert plan_scale._parse_dimension_text("20'") == pytest.approx(20.0)
    assert plan_scale._parse_dimension_text("not a dimension") is None


def test_ocr_calibration_requires_pytesseract_or_returns_none():
    pytesseract = pytest.importorskip("pytesseract", reason="Method 2 (OCR) is an optional assist")
    # If pytesseract IS installed, exercising the real OCR call needs a real
    # image with legible text; that belongs in an integration test against a
    # real plan fixture, not this unit test. Here we only confirm the
    # low-sample-count path degrades to None rather than a low-confidence guess.
    walls = [WallSegment(id="w1", a_px=(0, 0), b_px=(100, 0), thickness_px=6, confidence=1.0)]
    import numpy as np
    blank_gray = np.full((50, 200), 255, dtype="uint8")
    cal = plan_scale.calibrate_from_ocr(blank_gray, walls, min_matches=3)
    assert cal is None
