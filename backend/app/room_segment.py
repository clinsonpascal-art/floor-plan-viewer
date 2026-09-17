"""Deterministic room-boundary extraction from detected wall segments.

Vector-first, not raw-pixel flood-fill: a wall with a doorway cut into it is
still one continuous partition for room-boundary purposes (the opening is
attached as metadata in a later phase, not a topological break here). Walls
are noded into a planar line arrangement and its bounded faces are taken
directly as room polygons - no separate "exterior" polygon needs filtering,
since shapely.ops.polygonize never returns the unbounded face.
"""
from __future__ import annotations

import math
import uuid

from shapely.geometry import LineString, Polygon
from shapely.ops import polygonize, unary_union

from .plan_geom_types import RoomPolygon, WallSegment


def _point_segment_distance(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
    """Plain-python point-to-segment distance, used in place of building a
    shapely LineString/Point per candidate wall - this runs O(rooms *
    vertices * walls) times, and shapely object construction overhead
    dominates the cost at real-plan wall counts (profiled at ~2s alone on
    the Continuum sample)."""
    dx, dy = bx - ax, by - ay
    length2 = dx * dx + dy * dy
    if length2 < 1e-12:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length2))
    cx, cy = ax + t * dx, ay + t * dy
    return math.hypot(px - cx, py - cy)


def _snap_endpoints(walls: list[WallSegment], tol_px: float) -> list[LineString]:
    """Merge near-miss endpoints (within tol_px) to a shared point before noding."""
    points: list[tuple[float, float]] = []
    for w in walls:
        points.append(w.a_px)
        points.append(w.b_px)

    clusters: list[list[int]] = []
    assigned = [-1] * len(points)
    for i, p in enumerate(points):
        if assigned[i] != -1:
            continue
        cluster_id = len(clusters)
        clusters.append([i])
        assigned[i] = cluster_id
        for j in range(i + 1, len(points)):
            if assigned[j] != -1:
                continue
            q = points[j]
            if ((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2) ** 0.5 <= tol_px:
                clusters[cluster_id].append(j)
                assigned[j] = cluster_id

    resolved = list(points)
    for cluster in clusters:
        if len(cluster) < 2:
            continue
        cx = sum(points[i][0] for i in cluster) / len(cluster)
        cy = sum(points[i][1] for i in cluster) / len(cluster)
        for i in cluster:
            resolved[i] = (cx, cy)

    lines = []
    for idx, w in enumerate(walls):
        a = resolved[idx * 2]
        b = resolved[idx * 2 + 1]
        if a == b:
            continue
        # Extend both ends slightly so a wall whose detected endpoint falls
        # a little short of a T-junction (common with imperfect corner/wall
        # detection) still geometrically crosses the wall it abuts, letting
        # shapely's noding close the room polygon correctly instead of
        # leaving a sliver gap that breaks polygonize's face detection.
        ext = max(3.0, w.thickness_px / 2.0 + 2.0)
        length = math.hypot(b[0] - a[0], b[1] - a[1])
        if length < 1e-6:
            continue
        ux, uy = (b[0] - a[0]) / length, (b[1] - a[1]) / length
        a_ext = (a[0] - ux * ext, a[1] - uy * ext)
        b_ext = (b[0] + ux * ext, b[1] + uy * ext)
        lines.append(LineString([a_ext, b_ext]))
    return lines


def _match_walls_to_boundary(boundary: list[tuple[float, float]], walls: list[WallSegment]) -> list[str]:
    """For each boundary edge, the id of the nearest known wall to its
    midpoint - the same nearest-wall attribution used when a room polygon is
    first extracted from the noded arrangement, factored out so a merged
    polygon's boundary can be re-attributed the same way."""
    wall_ids = []
    n = len(boundary)
    for i in range(n):
        p0 = boundary[i]
        p1 = boundary[(i + 1) % n]
        mid = ((p0[0] + p1[0]) / 2.0, (p0[1] + p1[1]) / 2.0)
        best_wall, best_dist = None, float("inf")
        for w in walls:
            d = _point_segment_distance(mid[0], mid[1], w.a_px[0], w.a_px[1], w.b_px[0], w.b_px[1])
            if d < best_dist:
                best_dist, best_wall = d, w
        wall_ids.append(best_wall.id if best_wall else "")
    return wall_ids


# Both thresholds must hold before a small polygon is folded into a
# neighbor - see _merge_small_fragments's docstring for why each one exists.
_FRAGMENT_MIN_SHARED_PERIMETER_RATIO = 0.5
_FRAGMENT_MAX_AREA_RATIO = 0.35


def _edge_lengths_by_wall(room: RoomPolygon) -> dict[str, float]:
    """Length attributed to each wall_id along this room's own boundary
    (summed, in the rare case a single wall spans more than one edge)."""
    lengths: dict[str, float] = {}
    n = len(room.boundary_px)
    for i in range(n):
        wid = room.wall_ids[i] if i < len(room.wall_ids) else ""
        if not wid:
            continue
        p0 = room.boundary_px[i]
        p1 = room.boundary_px[(i + 1) % n]
        length = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
        lengths[wid] = lengths.get(wid, 0.0) + length
    return lengths


def _merge_fragment_into_neighbor(fragment: RoomPolygon, neighbor: RoomPolygon,
                                   walls: list[WallSegment]) -> RoomPolygon | None:
    """Union two adjacent room polygons into one, re-deriving boundary/area/
    wall_ids/centroid the same way segment() derives them for a fresh face.
    Keeps the (larger) neighbor's id so downstream references stay stable.
    Returns None if the two polygons don't union into one clean polygon
    (e.g. they only touch at a point) - the merge is skipped rather than
    risk corrupting geometry."""
    poly_a = Polygon(fragment.boundary_px)
    poly_b = Polygon(neighbor.boundary_px)
    if not poly_a.is_valid or not poly_b.is_valid:
        return None
    union = unary_union([poly_a, poly_b])
    if union.geom_type != "Polygon":
        return None

    simplified = union.simplify(2.0, preserve_topology=True)
    boundary = [(float(x), float(y)) for x, y in list(simplified.exterior.coords)[:-1]]
    wall_ids = _match_walls_to_boundary(boundary, walls)
    centroid = simplified.centroid
    return RoomPolygon(
        id=neighbor.id,
        boundary_px=boundary,
        wall_ids=wall_ids,
        area_px2=float(simplified.area),
        centroid_px=(float(centroid.x), float(centroid.y)),
    )


def _merge_small_fragments(rooms: list[RoomPolygon], walls: list[WallSegment]) -> list[RoomPolygon]:
    """Fold a small room polygon into an adjacent larger one when it looks
    like an over-segmentation artifact (a closet, nook, or double-wall
    sliver carved out of a bigger room) rather than a genuinely separate
    room, using only adjacency and relative size - never room names/types,
    which aren't known at this geometry-only stage anyway.

    A polygon is merged into the one neighbor it shares the most wall with
    only when BOTH hold:
      - shared perimeter ratio >= _FRAGMENT_MIN_SHARED_PERIMETER_RATIO: most
        of its own boundary is wall it shares with that neighbor. A real,
        separate room is mostly its own exterior/other walls, joined to a
        neighbor by only a doorway-width span - never a majority of its
        perimeter - so this alone rules out merging two true rooms.
      - area ratio <= _FRAGMENT_MAX_AREA_RATIO: it is small relative to that
        neighbor. Two genuinely separate rooms of comparable size (ratio
        near 1) never satisfy this even when adjacent.

    Runs to a fixed point so a chain of fragments folds into one final room.
    """
    by_id = {r.id: r for r in rooms}
    for _ in range(len(rooms) + 1):
        merged_this_pass = False
        for room in sorted(by_id.values(), key=lambda r: r.area_px2):
            edge_lengths = _edge_lengths_by_wall(room)
            perimeter = sum(edge_lengths.values())
            if perimeter <= 0:
                continue

            shared_by_neighbor: dict[str, float] = {}
            for other in by_id.values():
                if other.id == room.id:
                    continue
                shared = sum(length for wid, length in edge_lengths.items() if wid in other.wall_ids)
                if shared > 0:
                    shared_by_neighbor[other.id] = shared
            if not shared_by_neighbor:
                continue

            best_id = max(shared_by_neighbor, key=shared_by_neighbor.get)
            neighbor = by_id[best_id]
            if neighbor.area_px2 <= room.area_px2:
                continue

            shared_ratio = shared_by_neighbor[best_id] / perimeter
            area_ratio = room.area_px2 / neighbor.area_px2
            if shared_ratio < _FRAGMENT_MIN_SHARED_PERIMETER_RATIO or area_ratio > _FRAGMENT_MAX_AREA_RATIO:
                continue

            merged = _merge_fragment_into_neighbor(room, neighbor, walls)
            if merged is None:
                continue
            del by_id[room.id]
            del by_id[neighbor.id]
            by_id[merged.id] = merged
            merged_this_pass = True
            break
        if not merged_this_pass:
            break
    return list(by_id.values())


def segment(walls: list[WallSegment], min_room_area_px2: float, rectilinear_snap_deg: float = 0.0,
            merge_fragments: bool = True) -> list[RoomPolygon]:
    """Extract room polygons as the bounded faces of the wall-segment planar graph.

    min_room_area_px2: drops slivers from imperfect noding (not real rooms).
    rectilinear_snap_deg: if >0, snaps edges within this angle tolerance of
      0/90 degrees to exactly axis-aligned. Off by default so a genuinely
      angled wall (e.g. a curved terrace edge) is left alone.
    merge_fragments: fold small over-segmented sub-regions (closets/nooks)
      into their adjacent parent room - see _merge_small_fragments. On by
      default; callers that want the raw faces (e.g. tests) can disable it.
    """
    if not walls:
        return []

    tol = max(2.0, 0.5 * (sum(w.thickness_px for w in walls) / len(walls)))
    lines = _snap_endpoints(walls, tol)
    if not lines:
        return []

    noded = unary_union(lines)
    faces = list(polygonize(noded))

    rooms: list[RoomPolygon] = []
    for poly in faces:
        if poly.area < min_room_area_px2:
            continue
        simplified = poly.simplify(2.0, preserve_topology=True)
        boundary = [(float(x), float(y)) for x, y in list(simplified.exterior.coords)[:-1]]
        wall_ids = _match_walls_to_boundary(boundary, walls)
        centroid = simplified.centroid
        rooms.append(RoomPolygon(
            id=f"room_{uuid.uuid4().hex[:8]}",
            boundary_px=boundary,
            wall_ids=wall_ids,
            area_px2=float(simplified.area),
            centroid_px=(float(centroid.x), float(centroid.y)),
        ))

    if merge_fragments:
        rooms = _merge_small_fragments(rooms, walls)
    return rooms
