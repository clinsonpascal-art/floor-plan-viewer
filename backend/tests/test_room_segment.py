"""Phase 1 accuracy test: room-boundary extraction.

Accuracy is graded against the synthetic fixture (exact known ground truth).
The real uploaded Continuum plan is exercised as a smoke test only - see
test_real_plan_smoke - since it cannot be hand-annotated to reliable
pixel-exact ground truth (see fixtures/synthetic_plan.py docstring).
"""
from pathlib import Path

from shapely.geometry import Polygon

from app import room_segment, wall_detect
from app.plan_preprocess import _binarize, preprocess

from fixtures.synthetic_plan import EXPECTED_ROOMS, build_synthetic_plan

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_PLAN = REPO_ROOT / "backend" / "source_continuum_residence_01.jpg"


def _iou(poly_a: Polygon, poly_b: Polygon) -> float:
    inter = poly_a.intersection(poly_b).area
    union = poly_a.union(poly_b).area
    return inter / union if union else 0.0


def test_room_count_and_iou_against_synthetic_ground_truth():
    img = build_synthetic_plan()
    mask = _binarize(img, "otsu")
    walls = wall_detect.detect(mask, min_wall_len_px=40)
    rooms = room_segment.segment(walls, min_room_area_px2=500)

    assert len(rooms) == len(EXPECTED_ROOMS)

    gt_polys = [Polygon(pts) for pts in EXPECTED_ROOMS]
    det_polys = [Polygon(r.boundary_px) for r in rooms]

    # Match each ground-truth room to its best-IoU detected room.
    used = set()
    ious = []
    for gt_poly in gt_polys:
        best_iou, best_j = 0.0, None
        for j, det_poly in enumerate(det_polys):
            if j in used:
                continue
            iou = _iou(gt_poly, det_poly)
            if iou > best_iou:
                best_iou, best_j = iou, j
        assert best_j is not None
        used.add(best_j)
        ious.append(best_iou)

    assert min(ious) >= 0.85, ious
    assert sum(ious) / len(ious) >= 0.9, ious


def test_wall_id_adjacency_is_shared_between_rooms():
    """The two synthetic rooms share three wall spans in this layout: the
    interior partition (dividing them), plus the single continuous top wall
    and single continuous bottom wall that each run along both rooms'
    exteriors (this is a single outer rectangle + one internal divider, so
    top/bottom are genuinely one shared wall each, not per-room copies).
    The specific adjacency property worth asserting is that the *interior
    partition* - identifiable as the one shared wall whose centerline sits
    away from the outer perimeter - is correctly recognized as shared."""
    img = build_synthetic_plan()
    mask = _binarize(img, "otsu")
    walls = wall_detect.detect(mask, min_wall_len_px=40)
    rooms = room_segment.segment(walls, min_room_area_px2=500)
    assert len(rooms) == 2

    ids_a = set(rooms[0].wall_ids)
    ids_b = set(rooms[1].wall_ids)
    shared = ids_a & ids_b
    assert len(shared) >= 1

    by_id = {w.id: w for w in walls}
    partition = min(walls, key=lambda w: abs((w.a_px[0] + w.b_px[0]) / 2.0 - 200.0))
    assert partition.id in shared, "the interior partition wall must be recognized as shared by both rooms"


def test_real_plan_smoke():
    """Sanity check only (no accuracy assertion) against the actual uploaded
    plan image, to confirm the pipeline runs end to end on real, messy pixels
    without crashing and produces a plausible number of walls/rooms."""
    if not REAL_PLAN.exists():
        return
    result = preprocess(REAL_PLAN)
    walls = wall_detect.detect(result.mask, min_wall_len_px=30)
    rooms = room_segment.segment(walls, min_room_area_px2=2000)

    assert len(walls) > 5
    assert 1 <= len(rooms) <= 40
