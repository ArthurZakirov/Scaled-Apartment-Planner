#!/usr/bin/env python3
"""Validate the structured floor plan and the currently active furniture layout."""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

try:
    from shapely.affinity import rotate, translate
    from shapely.geometry import LineString, Point, Polygon
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Install dependencies first: python3 -m pip install -r requirements.txt") from exc

ROOT = Path(__file__).resolve().parents[1]


def load_json(relative: str) -> dict[str, Any]:
    with (ROOT / relative).open(encoding="utf-8") as handle:
        return json.load(handle)


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


def main() -> int:
    apartment = load_json("data/apartment.json")
    furniture = load_json("data/furniture.json")
    constraints = load_json("data/layout-constraints.json")

    errors: list[str] = []
    warnings: list[str] = []

    validation_file = apartment["source"].get("validationFile")
    if validation_file:
        source_path = ROOT / validation_file
        if source_path.exists():
            actual_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
            if actual_hash != apartment["source"]["sha256"]:
                errors.append("The immutable source image hash changed.")
        else:
            warnings.append(f"Optional local source copy not present: {validation_file}")
    elif not apartment["source"].get("originalUrl"):
        errors.append("No immutable source image URL or validation file is configured.")

    view_x, view_y, view_width, view_height = apartment["coordinateSystem"]["viewBox"]
    view_polygon = Polygon(
        [
            (view_x, view_y),
            (view_x + view_width, view_y),
            (view_x + view_width, view_y + view_height),
            (view_x, view_y + view_height),
        ]
    )

    spaces: dict[str, Polygon] = {}
    for space in apartment["spaces"]:
        polygon = Polygon(space["points"])
        spaces[space["id"]] = polygon
        if not polygon.is_valid:
            errors.append(f"Space {space['id']} is invalid/self-intersecting.")
        if not view_polygon.covers(polygon):
            errors.append(f"Space {space['id']} leaves the configured viewBox.")

    for wall in apartment["walls"]:
        if wall["start"] == wall["end"]:
            errors.append(f"Wall {wall['id']} has zero length.")
        line = LineString([wall["start"], wall["end"]])
        if not view_polygon.buffer(1).covers(line):
            errors.append(f"Wall {wall['id']} leaves the configured viewBox.")

    door_ids = [door["id"] for door in apartment["doors"]]
    if len(door_ids) != len(set(door_ids)):
        errors.append("Door IDs are not unique.")

    active_layout = next((item for item in furniture["layouts"] if item["id"] == furniture["activeLayoutId"]), None)
    if active_layout is None:
        errors.append("Active layout does not exist.")
        return finish(errors, warnings)

    cm_per_pixel = apartment["scale"]["cmPerPixel"]
    object_polygons: dict[str, Polygon] = {}
    for obj in active_layout["objects"]:
        polygon = furniture_polygon(obj, cm_per_pixel)
        object_polygons[obj["id"]] = polygon
        if not polygon.is_valid:
            errors.append(f"Furniture {obj['id']} has invalid geometry.")
        if not spaces["space-main"].buffer(5).covers(polygon):
            errors.append(f"Furniture {obj['id']} leaves the approximate interior by more than the 5 px reconstruction tolerance.")

    object_ids = list(object_polygons)
    for index, first_id in enumerate(object_ids):
        for second_id in object_ids[index + 1 :]:
            overlap = object_polygons[first_id].intersection(object_polygons[second_id]).area
            if overlap > 0.5:
                errors.append(f"Furniture overlap: {first_id} and {second_id} overlap by {overlap:.1f} px².")

    required = set(constraints["doorPolicies"]["mustRemainUsable"])
    permitted = set(constraints["doorPolicies"]["mayBeBlocked"])
    intentionally_blocked = {
        door_id
        for obj in active_layout["objects"]
        for door_id in obj.get("intentionalDoorBlocks", [])
    }

    blocked_door_ids: set[str] = set()
    for door in apartment["doors"]:
        zone = door_swing_polygon(door)
        blockers = [obj_id for obj_id, polygon in object_polygons.items() if zone.intersects(polygon)]
        if blockers:
            blocked_door_ids.add(door["id"])
            if door["id"] in required:
                errors.append(f"Required door {door['id']} is blocked by {', '.join(blockers)}.")
            elif door["id"] not in permitted:
                warnings.append(f"Door {door['id']} is blocked but has no explicit policy.")

    missing_intentional_blocks = intentionally_blocked - blocked_door_ids
    if missing_intentional_blocks:
        warnings.append("Objects declare intentional blocks that are not detected: " + ", ".join(sorted(missing_intentional_blocks)))

    if not ({"door-loggia-bedroom", "door-loggia-living"} - blocked_door_ids):
        errors.append("Both loggia doors are blocked.")
    if not ({"door-balcony-upper", "door-balcony-lower"} - blocked_door_ids):
        errors.append("Both balcony doors are blocked.")

    if apartment["scale"]["status"] != "confirmed":
        warnings.append("Entrance-door anchor is confirmed, but real-world clearances remain estimates because the source is not to scale.")

    return finish(errors, warnings, active_layout["id"], blocked_door_ids)


def finish(errors: list[str], warnings: list[str], layout_id: str | None = None, blocked: set[str] | None = None) -> int:
    print("Scaled Apartment Planner validation")
    if layout_id:
        print(f"  layout: {layout_id}")
    if blocked is not None:
        print(f"  blocked doors: {', '.join(sorted(blocked)) or 'none'}")
    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        print(f"FAILED with {len(errors)} error(s).")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
