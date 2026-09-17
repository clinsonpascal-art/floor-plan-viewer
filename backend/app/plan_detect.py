"""Phase 4: deterministic floor-plan detection orchestrator.

Wires plan_preprocess -> plan_scale -> wall_detect -> room_segment ->
opening_detect into one call that turns an ARBITRARY uploaded floor-plan
image into rooms/walls/openings with measurements - not just the authored
Residence A / Continuum templates.

Room TYPE/NAME (e.g. "this polygon is the kitchen") cannot be determined from
wall/room geometry alone - it requires reading a printed label. This module
never guesses it: it returns geometry only. Naming is layered on separately
by an optional vision-assist step (see plan_parser.py) that assigns a name to
a REAL, already-detected polygon - it never invents room boundaries or
dimensions itself.

No AI/vision-model call in this module - pure OpenCV + shapely geometry.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import opening_detect, plan_scale, room_segment, wall_detect
from .plan_geom_types import Opening, RoomPolygon, ScaleCalibration, WallSegment
from .plan_preprocess import preprocess


@dataclass
class DetectedPlan:
    size_px: tuple[int, int]
    rotation_deg: float
    walls: list[WallSegment]
    rooms: list[RoomPolygon]
    openings: list[Opening]
    scale: ScaleCalibration | None
    warnings: list[str] = field(default_factory=list)


MIN_WALL_CONFIDENCE = 0.5


def _drop_low_confidence_walls(walls: list[WallSegment]) -> list[WallSegment]:
    """wall_detect's collinear clustering can merge sparse, unrelated marks
    (e.g. two fragments of a door-swing-arc curve near the same angle/offset)
    into one long "wall" with very low actual pixel coverage. A real wall
    covers most of its own inferred span (see wall_detect.WallSegment.confidence,
    tested at >0.7 for a clean plan) - drop anything far below that rather than
    let a phantom partition corrupt room segmentation."""
    return [w for w in walls if w.confidence >= MIN_WALL_CONFIDENCE]


def _bootstrap_min_wall_len_px(size_px: tuple[int, int]) -> float:
    """Before scale is known, use a fraction of the image's own diagonal as the
    shortest plausible wall length, rather than a fixed pixel constant that
    would be wrong for a much smaller or larger upload than expected."""
    w, h = size_px
    diag = (w ** 2 + h ** 2) ** 0.5
    return max(20.0, diag * 0.03)


def detect_plan(image_path: Path, total_interior_sqft: float | None = None,
                 manual_scale: ScaleCalibration | None = None) -> DetectedPlan:
    """Run the full deterministic detection pipeline on an arbitrary floor-plan
    image.

    total_interior_sqft: an already-known total (e.g. read from printed text
    by an optional caller-side step) - enables the lowest-confidence
    total_area_anchor scale method. Never guessed inside this function.
    manual_scale: an operator-supplied calibration, if one exists. Takes
    priority over automatic OCR/area calibration.
    """
    warnings: list[str] = []
    pre = preprocess(image_path)

    bootstrap_len = _bootstrap_min_wall_len_px(pre.size_px)
    walls = _drop_low_confidence_walls(wall_detect.detect(pre.mask, min_wall_len_px=bootstrap_len))
    if not walls:
        warnings.append("no_walls_detected")
        return DetectedPlan(pre.size_px, pre.rotation_deg, [], [], [], None, warnings)

    scale = manual_scale
    if scale is None:
        scale = plan_scale.calibrate_from_ocr(pre.gray, walls)
    if scale is None and total_interior_sqft:
        bootstrap_rooms = room_segment.segment(walls, min_room_area_px2=bootstrap_len ** 2)
        total_area_px2 = sum(r.area_px2 for r in bootstrap_rooms)
        if total_area_px2 > 0:
            scale = plan_scale.calibrate_from_total_area(total_interior_sqft, total_area_px2)
    if scale is None:
        warnings.append("no_scale_reference_dimensions_unavailable")

    # Re-detect with a scale-informed minimum wall length so a real short wall
    # isn't dropped and a stray smudge isn't kept, now that "2 real feet" has
    # a known meaning in this image's own pixel scale.
    if scale:
        min_len = max(20.0, 2.0 * scale.px_per_ft)
        walls = _drop_low_confidence_walls(wall_detect.detect(pre.mask, min_wall_len_px=min_len))
        if not walls:
            warnings.append("no_walls_detected")
            return DetectedPlan(pre.size_px, pre.rotation_deg, [], [], [], scale, warnings)

    min_room_area_px2 = (4.0 * scale.px_per_ft) ** 2 if scale else bootstrap_len ** 2
    rooms = room_segment.segment(walls, min_room_area_px2=min_room_area_px2)
    if not rooms:
        warnings.append("no_rooms_segmented")

    openings = opening_detect.detect_openings(
        walls, pre.mask, pre.gray, px_per_ft=scale.px_per_ft if scale else None
    )

    return DetectedPlan(pre.size_px, pre.rotation_deg, walls, rooms, openings, scale, warnings)


def room_dimensions_ft(room: RoomPolygon, scale: ScaleCalibration | None) -> tuple[float | None, float | None]:
    """Axis-aligned bounding width/depth of the room polygon, in feet - only
    when a real scale calibration is available. Never fabricated."""
    if not scale or not room.boundary_px:
        return None, None
    xs = [p[0] for p in room.boundary_px]
    ys = [p[1] for p in room.boundary_px]
    width_px = max(xs) - min(xs)
    depth_px = max(ys) - min(ys)
    return round(width_px / scale.px_per_ft, 2), round(depth_px / scale.px_per_ft, 2)


def infer_connections(rooms: list[RoomPolygon], openings: list[Opening]) -> dict[str, set[str]]:
    """Two rooms are connected when they share a wall that has a real detected
    door/unknown opening in it - derived purely from geometry, never guessed."""
    conn: dict[str, set[str]] = {r.id: set() for r in rooms}
    wall_to_rooms: dict[str, list[str]] = {}
    for r in rooms:
        for wid in r.wall_ids:
            wall_to_rooms.setdefault(wid, []).append(r.id)
    doorish_walls = {o.wall_id for o in openings if o.kind in ("door", "unknown_opening")}
    for wid, rids in wall_to_rooms.items():
        if wid not in doorish_walls or len(rids) < 2:
            continue
        for i in range(len(rids)):
            for j in range(i + 1, len(rids)):
                if rids[i] != rids[j]:
                    conn[rids[i]].add(rids[j])
                    conn[rids[j]].add(rids[i])
    return conn


def openings_for_room(room: RoomPolygon, openings: list[Opening]) -> list[Opening]:
    wall_ids = set(room.wall_ids)
    return [o for o in openings if o.wall_id in wall_ids]
