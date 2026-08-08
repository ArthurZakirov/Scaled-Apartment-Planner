"""Geometric furniture-scenario evaluation shared by validation and export tools."""

from __future__ import annotations

import math
from typing import Any

from shapely.affinity import rotate, translate
from shapely.geometry import Polygon
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


def evaluate_layout(
    layout: dict[str, Any], apartment: dict[str, Any], constraints: dict[str, Any]
) -> dict[str, Any]:
    cm_per_pixel = apartment["scale"]["cmPerPixel"]
    interior = Polygon(next(space["points"] for space in apartment["spaces"] if space["id"] == "space-main"))
    object_polygons: dict[str, Polygon] = {}
    reasons: list[str] = []
    collisions: list[str] = []

    for obj in layout["objects"]:
        polygon = furniture_polygon(obj, cm_per_pixel)
        object_polygons[obj["id"]] = polygon
        if not polygon.is_valid:
            reasons.append(f"Furniture {obj['id']} has invalid geometry.")
        if not interior.buffer(5).covers(polygon):
            reasons.append(f"Furniture {obj['id']} leaves the approximate interior.")

    object_ids = list(object_polygons)
    pair_distances: list[float] = []
    for index, first_id in enumerate(object_ids):
        for second_id in object_ids[index + 1 :]:
            first = object_polygons[first_id]
            second = object_polygons[second_id]
            overlap = first.intersection(second).area
            pair_distances.append(first.distance(second) * cm_per_pixel)
            if overlap > 0.5:
                collision = f"{first_id} ↔ {second_id} ({overlap:.1f}px²)"
                collisions.append(collision)
                reasons.append(f"Furniture overlap: {collision}.")

    blocked_by: dict[str, list[str]] = {}
    for door in apartment["doors"]:
        zone = door_swing_polygon(door)
        blockers = [obj_id for obj_id, polygon in object_polygons.items() if zone.intersects(polygon)]
        if blockers:
            blocked_by[door["id"]] = blockers

    required = set(constraints["doorPolicies"]["mustRemainUsable"])
    for door_id in sorted(required & blocked_by.keys()):
        reasons.append(f"Required door {door_id} is blocked by {', '.join(blocked_by[door_id])}.")
    if not ({"door-loggia-bedroom", "door-loggia-living"} - blocked_by.keys()):
        reasons.append("Both loggia doors are blocked.")
    if not ({"door-balcony-upper", "door-balcony-lower"} - blocked_by.keys()):
        reasons.append("Both balcony doors are blocked.")

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
        "blockedBy": blocked_by,
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
