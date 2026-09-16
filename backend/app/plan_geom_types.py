"""Shared data structures for the deterministic floor-plan geometry pipeline
(Phase 1: scale calibration, wall detection, room boundary extraction).

Pure data, no logic. These are the interfaces between plan_preprocess.py,
plan_scale.py, wall_detect.py and room_segment.py, and the contract that
later phases (opening detection, 3D mesh assembly) build on.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class ScaleCalibration:
    px_per_ft: float
    source: Literal["manual_reference", "dimension_text_ocr", "total_area_anchor"]
    confidence: float
    sample_count: int | None = None


@dataclass
class WallSegment:
    id: str
    a_px: tuple[float, float]
    b_px: tuple[float, float]
    thickness_px: float
    confidence: float

    def length_px(self) -> float:
        return ((self.b_px[0] - self.a_px[0]) ** 2 + (self.b_px[1] - self.a_px[1]) ** 2) ** 0.5


@dataclass
class RoomPolygon:
    id: str
    boundary_px: list[tuple[float, float]]
    wall_ids: list[str] = field(default_factory=list)
    area_px2: float = 0.0
    centroid_px: tuple[float, float] = (0.0, 0.0)
