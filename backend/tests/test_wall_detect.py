"""Phase 1 accuracy test: wall detection against a synthetic plan with exact,
known ground truth (see tests/fixtures/synthetic_plan.py for why synthetic,
not the real ornate Continuum plan, is used for accuracy grading)."""
import math

import cv2
import numpy as np
import pytest
from scipy.optimize import linear_sum_assignment

from app import wall_detect
from app.plan_preprocess import _binarize

from fixtures.synthetic_plan import EXPECTED_WALLS, build_synthetic_plan


def _angle_deg(a, b):
    return math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) % 180.0


def _endpoint_error(a_gt, b_gt, a_det, b_det):
    d1 = math.hypot(a_gt[0] - a_det[0], a_gt[1] - a_det[1]) + math.hypot(b_gt[0] - b_det[0], b_gt[1] - b_det[1])
    d2 = math.hypot(a_gt[0] - b_det[0], a_gt[1] - b_det[1]) + math.hypot(b_gt[0] - a_det[0], b_gt[1] - a_det[1])
    return min(d1, d2) / 2.0


@pytest.fixture(scope="module")
def detected_walls():
    img = build_synthetic_plan()
    mask = _binarize(img, "otsu")
    return wall_detect.detect(mask, min_wall_len_px=40)


def test_wall_count_matches_ground_truth(detected_walls):
    assert len(detected_walls) == len(EXPECTED_WALLS)


def test_wall_geometry_matches_ground_truth(detected_walls):
    gt = EXPECTED_WALLS
    det = detected_walls
    cost = np.zeros((len(gt), len(det)))
    for i, (a_gt, b_gt) in enumerate(gt):
        for j, w in enumerate(det):
            err = _endpoint_error(a_gt, b_gt, w.a_px, w.b_px)
            ang_gt = _angle_deg(a_gt, b_gt)
            ang_det = _angle_deg(w.a_px, w.b_px)
            d_ang = min(abs(ang_gt - ang_det), 180.0 - abs(ang_gt - ang_det))
            cost[i, j] = err + d_ang * 5.0  # weighted combination
    rows, cols = linear_sum_assignment(cost)

    endpoint_errors = []
    angle_errors = []
    thickness_errors = []
    for i, j in zip(rows, cols):
        a_gt, b_gt = gt[i]
        w = det[j]
        endpoint_errors.append(_endpoint_error(a_gt, b_gt, w.a_px, w.b_px))
        ang_gt = _angle_deg(a_gt, b_gt)
        ang_det = _angle_deg(w.a_px, w.b_px)
        angle_errors.append(min(abs(ang_gt - ang_det), 180.0 - abs(ang_gt - ang_det)))
        thickness_errors.append(abs(w.thickness_px - 6.0))

    assert max(endpoint_errors) < 6.0, endpoint_errors
    assert max(angle_errors) < 3.0, angle_errors
    assert max(thickness_errors) < 3.0, thickness_errors


def test_wall_confidence_is_high_on_clean_synthetic_plan(detected_walls):
    assert all(w.confidence > 0.7 for w in detected_walls)
