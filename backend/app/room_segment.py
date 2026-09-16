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

from shapely.geometry import LineString, Point
from shapely.ops import polygonize, unary_union

from .plan_geom_types import RoomPolygon, WallSegment


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


def segment(walls: list[WallSegment], min_room_area_px2: float, rectilinear_snap_deg: float = 0.0) -> list[RoomPolygon]:
    """Extract room polygons as the bounded faces of the wall-segment planar graph.

    min_room_area_px2: drops slivers from imperfect noding (not real rooms).
    rectilinear_snap_deg: if >0, snaps edges within this angle tolerance of
      0/90 degrees to exactly axis-aligned. Off by default so a genuinely
      angled wall (e.g. a curved terrace edge) is left alone.
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
        boundary = list(simplified.exterior.coords)[:-1]  # drop closing duplicate

        wall_ids = []
        for i in range(len(boundary)):
            p0 = boundary[i]
            p1 = boundary[(i + 1) % len(boundary)]
            mid = ((p0[0] + p1[0]) / 2.0, (p0[1] + p1[1]) / 2.0)
            best_wall, best_dist = None, float("inf")
            for w in walls:
                seg = LineString([w.a_px, w.b_px])
                d = seg.distance(Point(mid))
                if d < best_dist:
                    best_dist, best_wall = d, w
            wall_ids.append(best_wall.id if best_wall else "")

        centroid = simplified.centroid
        rooms.append(RoomPolygon(
            id=f"room_{uuid.uuid4().hex[:8]}",
            boundary_px=[(float(x), float(y)) for x, y in boundary],
            wall_ids=wall_ids,
            area_px2=float(simplified.area),
            centroid_px=(float(centroid.x), float(centroid.y)),
        ))
    return rooms
