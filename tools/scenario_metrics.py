"""Geometric furniture-scenario evaluation shared by validation and export tools."""

from __future__ import annotations

import math
from typing import Any

from shapely.affinity import rotate, translate
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union


def furniture_polygon(obj: dict[str, Any], cm_per_pixel: float) -> Polygon:
    dimensions = obj["dimensionsCm"]
    position = obj["positionPx"]
    shape = obj["render"]["shape"]

    if shape == "l_desk":
        width = dimensions["width"] / cm_per_pixel
        depth = dimensions["depth"] / cm_per_pixel
        main_depth = dimensions["mainTopDepth"] / cm_per_pixel
        return_depth = dimensions["returnDepth"] / cm_per_pixel
        x, y = position["topLeft"]
        if position.get("handedness") == "left":
            points = [(0, 0), (width, 0), (width, main_depth), (return_depth, main_depth), (return_depth, depth), (0, depth)]
        else:
            points = [(0, 0), (width, 0), (width, depth), (width - return_depth, depth), (width - return_depth, main_depth), (0, main_depth)]
        polygon = Polygon(points)
        polygon = rotate(polygon, position.get("rotationDeg", 0), origin=(0, 0), use_radians=False)
        return translate(polygon, xoff=x, yoff=y)

    width = dimensions["width"] / cm_per_pixel
    depth = dimensions["depth"] / cm_per_pixel
    cx, cy = position["center"]
    polygon = Polygon([(-width / 2, -depth / 2), (width / 2, -depth / 2), (width / 2, depth / 2), (-width / 2, depth / 2)])
    polygon = rotate(polygon, position.get("rotationDeg", 0), origin=(0, 0), use_radians=False)
    return translate(polygon, xoff=cx, yoff=cy)


def wall_solid_polygon(wall: dict[str, Any]) -> Polygon:
    """Expand a wall centerline into its physical solid using its modeled thickness."""
    return LineString([wall["start"], wall["end"]]).buffer(
        wall["thicknessPx"] / 2, cap_style=2, join_style=2
    )


def door_swing_polygon(door: dict[str, Any], steps: int = 36) -> Polygon:
    hx, hy = door["hinge"]
    closed = door["closedPoint"]
    opened = door["openPoint"]
    start = math.atan2(closed[1] - hy, closed[0] - hx)
    end = math.atan2(opened[1] - hy, opened[0] - hx)
    delta = (end - start + math.pi) % (2 * math.pi) - math.pi
    radius = max(math.dist((hx, hy), closed), math.dist((hx, hy), opened))
    points = [(hx, hy)]
    points.extend(
        (hx + radius * math.cos(start + delta * index / steps), hy + radius * math.sin(start + delta * index / steps))
        for index in range(steps + 1)
    )
    return Polygon(points)


def wardrobe_access_polygon(obj: dict[str, Any], cm_per_pixel: float, depth_cm: float = 45) -> Polygon:
    """Return a rectangular access strip at an object's negative-depth opening edge."""
    wardrobe = furniture_polygon(obj, cm_per_pixel)
    start, end = list(wardrobe.exterior.coords)[:2]
    edge_x, edge_y = end[0] - start[0], end[1] - start[1]
    normal_x, normal_y = -edge_y, edge_x
    normal_length = math.hypot(normal_x, normal_y)
    normal_x, normal_y = normal_x / normal_length, normal_y / normal_length
    midpoint = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
    center = wardrobe.centroid
    if math.dist((midpoint[0] + normal_x, midpoint[1] + normal_y), (center.x, center.y)) < math.dist(
        (midpoint[0] - normal_x, midpoint[1] - normal_y), (center.x, center.y)
    ):
        normal_x, normal_y = -normal_x, -normal_y
    depth_px = depth_cm / cm_per_pixel
    return Polygon(
        [
            start,
            end,
            (end[0] + normal_x * depth_px, end[1] + normal_y * depth_px),
            (start[0] + normal_x * depth_px, start[1] + normal_y * depth_px),
        ]
    )


def evaluate_layout(
    layout: dict[str, Any], apartment: dict[str, Any], constraints: dict[str, Any]
) -> dict[str, Any]:
    cm_per_pixel = apartment["scale"]["cmPerPixel"]
    interior = Polygon(next(space["points"] for space in apartment["spaces"] if space["id"] == "space-main"))
    object_polygons: dict[str, Polygon] = {}
    objects_by_id = {obj["id"]: obj for obj in layout["objects"]}
    reasons: list[str] = []
    collisions: list[str] = []
    interior_wall_collisions: list[str] = []
    interior_wall_solids = {
        wall["id"]: wall_solid_polygon(wall)
        for wall in apartment["walls"]
        if wall.get("kind") == "interior"
    }

    for obj in layout["objects"]:
        polygon = furniture_polygon(obj, cm_per_pixel)
        object_polygons[obj["id"]] = polygon
        if not polygon.is_valid:
            reasons.append(f"Furniture {obj['id']} has invalid geometry.")
        if not interior.buffer(5).covers(polygon):
            reasons.append(f"Furniture {obj['id']} leaves the approximate interior.")
        for wall_id, wall_solid in interior_wall_solids.items():
            overlap = polygon.intersection(wall_solid).area
            if overlap > 0.5:
                collision = f"{obj['id']} ↔ {wall_id} ({overlap:.1f}px²)"
                interior_wall_collisions.append(collision)
                reasons.append(f"Furniture crosses fixed interior wall: {collision}.")

    object_ids = list(object_polygons)
    pair_distances: list[float] = []
    for index, first_id in enumerate(object_ids):
        for second_id in object_ids[index + 1 :]:
            first = object_polygons[first_id]
            second = object_polygons[second_id]
            overlap = first.intersection(second).area
            pair_types = {objects_by_id[first_id]["type"], objects_by_id[second_id]["type"]}
            if pair_types != {"bed", "storage"}:
                pair_distances.append(first.distance(second) * cm_per_pixel)
            if overlap > 0.5:
                collision = f"{first_id} ↔ {second_id} ({overlap:.1f}px²)"
                collisions.append(collision)
                reasons.append(f"Furniture overlap: {collision}.")

    wardrobe_access_blocked_by: list[str] = []
    wardrobe_access_depth_cm = layout.get("selection", {}).get(
        "paxAccessDepthCm", constraints.get("wardrobeAccessDepthCm", 45)
    )
    for wardrobe in (obj for obj in layout["objects"] if obj["type"] == "wardrobe"):
        if wardrobe_access_depth_cm <= 0:
            continue
        access_zone = wardrobe_access_polygon(
            wardrobe, cm_per_pixel, wardrobe_access_depth_cm
        )
        if not interior.buffer(5).covers(access_zone):
            wardrobe_access_blocked_by.append("interior-boundary")
            reasons.append("Wardrobe access leaves the approximate interior.")
        for other in (obj for obj in layout["objects"] if obj["id"] != wardrobe["id"]):
            if access_zone.intersection(object_polygons[other["id"]]).area > 0.5:
                wardrobe_access_blocked_by.append(other["id"])
                reasons.append(f"Wardrobe access is blocked by {other['id']}.")
        for door in apartment["doors"]:
            if access_zone.intersection(door_swing_polygon(door)).area > 0.5:
                wardrobe_access_blocked_by.append(door["id"])
                reasons.append(f"Wardrobe access conflicts with {door['id']}.")

    storage_access_blocked_by: list[str] = []
    for storage in (
        obj for obj in layout["objects"] if obj["type"] == "storage" and obj.get("accessLabel")
    ):
        access_zone = wardrobe_access_polygon(
            storage, cm_per_pixel, storage.get("accessDepthCm", constraints.get("storageAccessDepthCm", 35))
        )
        if not interior.buffer(5).covers(access_zone):
            storage_access_blocked_by.append("interior-boundary")
            reasons.append(f"Storage access for {storage['id']} leaves the approximate interior.")
        for other in (obj for obj in layout["objects"] if obj["id"] != storage["id"]):
            if access_zone.intersection(object_polygons[other["id"]]).area > 0.5:
                storage_access_blocked_by.append(other["id"])
                reasons.append(f"Storage access for {storage['id']} is blocked by {other['id']}.")
        for door in apartment["doors"]:
            if access_zone.intersection(door_swing_polygon(door)).area > 0.5:
                storage_access_blocked_by.append(door["id"])
                reasons.append(f"Storage access for {storage['id']} conflicts with {door['id']}.")

    blocked_by: dict[str, list[str]] = {}
    for door in apartment["doors"]:
        zone = door_swing_polygon(door)
        blockers = [obj_id for obj_id, polygon in object_polygons.items() if zone.intersects(polygon)]
        if blockers:
            blocked_by[door["id"]] = blockers

    required = set(constraints["doorPolicies"]["mustRemainUsable"])
    for door_id in sorted(required & blocked_by.keys()):
        reasons.append(f"Required door {door_id} is blocked by {', '.join(blocked_by[door_id])}.")
    for group in constraints["doorPolicies"].get("atLeastOneUsableGroups", []):
        if not (set(group["doorIds"]) - blocked_by.keys()):
            reasons.append(f"At least one {group['label']} door must remain usable.")

    furniture_union = unary_union(list(object_polygons.values()))
    free_floor_px2 = max(0.0, interior.area - furniture_union.intersection(interior).area)
    free_floor_m2 = free_floor_px2 * (cm_per_pixel**2) / 10_000
    minimum_gap_cm = min(pair_distances) if pair_distances else 0.0
    usable_loggia = len({"door-loggia-bedroom", "door-loggia-living"} - blocked_by.keys())
    usable_balcony = len({"door-balcony-upper", "door-balcony-lower"} - blocked_by.keys())
    bed = next(obj for obj in layout["objects"] if obj["type"] == "bed")
    pax = next(obj for obj in layout["objects"] if obj["type"] == "wardrobe")
    desk = next(obj for obj in layout["objects"] if obj["type"] == "desk")
    bed_pax_gap_cm = object_polygons[bed["id"]].distance(object_polygons[pax["id"]]) * cm_per_pixel
    score = 0.0
    if not reasons:
        score = min(
            100.0,
            35
            + bed["mattressCm"]["width"] / 18
            + pax["dimensionsCm"]["width"] / 20
            + desk["dimensionsCm"]["width"] * desk["dimensionsCm"]["depth"] / 3000
            + min(minimum_gap_cm, 100) / 10,
        )

    return {
        "id": layout["id"],
        "name": layout["name"],
        "arrangementId": layout.get("arrangementId", "divider"),
        "installationStatus": layout.get("installationStatus", "requires_engineered_solution"),
        "valid": not reasons,
        "reasons": reasons,
        "collisions": collisions,
        "interiorWallCollisions": interior_wall_collisions,
        "blockedBy": blocked_by,
        "wardrobeAccessBlockedBy": wardrobe_access_blocked_by,
        "wardrobeAccessDepthCm": wardrobe_access_depth_cm,
        "storageAccessBlockedBy": storage_access_blocked_by,
        "minimumFurnitureGapCm": round(minimum_gap_cm, 1),
        "bedPaxGapCm": round(bed_pax_gap_cm, 1),
        "freeFloorAreaM2": round(free_floor_m2, 1),
        "usableLoggiaDoors": usable_loggia,
        "usableBalconyDoors": usable_balcony,
        "score": round(score, 1),
    }


def rank_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        (result for result in results if result["valid"]),
        key=lambda result: (
            0 if result.get("installationStatus") == "manufacturer_wall_mount_candidate" else 1,
            -result["score"],
            result["id"],
        ),
    )
