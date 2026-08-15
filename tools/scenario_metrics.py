"""Geometric furniture-scenario evaluation shared by validation and export tools."""

from __future__ import annotations

import math
from typing import Any

from shapely.affinity import rotate, translate
from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union

from desk_geometry import desk_work_zone_polygon, fixed_fixture_polygon, fixed_fixture_union


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


def door_opening_fraction(
    door: dict[str, Any], object_polygons: dict[str, Polygon], steps: int = 100
) -> tuple[float, list[str]]:
    """Return the unobstructed share of the door swing and its first blockers."""
    swing = door_swing_polygon(door)
    candidates = {
        obj_id: polygon for obj_id, polygon in object_polygons.items() if swing.intersects(polygon)
    }
    if not candidates:
        return 1.0, []

    hx, hy = door["hinge"]
    closed = door["closedPoint"]
    opened = door["openPoint"]
    start = math.atan2(closed[1] - hy, closed[0] - hx)
    end = math.atan2(opened[1] - hy, opened[0] - hx)
    delta = (end - start + math.pi) % (2 * math.pi) - math.pi
    radius = max(math.dist((hx, hy), closed), math.dist((hx, hy), opened))

    for index in range(steps + 1):
        angle = start + delta * index / steps
        leaf = LineString([(hx, hy), (hx + radius * math.cos(angle), hy + radius * math.sin(angle))])
        blockers = [obj_id for obj_id, polygon in candidates.items() if leaf.intersects(polygon)]
        if blockers:
            return max(0.0, (index - 1) / steps), blockers
    return 1.0, []


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
    layout: dict[str, Any],
    apartment: dict[str, Any],
    constraints: dict[str, Any],
    fixtures: dict[str, Any],
    fixed_furnishings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cm_per_pixel = apartment["scale"]["cmPerPixel"]
    interior = Polygon(next(space["points"] for space in apartment["spaces"] if space["id"] == "space-main"))
    object_polygons: dict[str, Polygon] = {}
    objects_by_id = {obj["id"]: obj for obj in layout["objects"]}
    reasons: list[str] = []
    collisions: list[str] = []
    interior_wall_collisions: list[str] = []
    exclusion_zones = {
        zone["id"]: (Polygon(zone["points"]), zone.get("tolerancePx2", 0.5))
        for zone in apartment.get("furnitureExclusionZones", [])
    }

    for obj in layout["objects"]:
        polygon = furniture_polygon(obj, cm_per_pixel)
        object_polygons[obj["id"]] = polygon
        if not polygon.is_valid:
            reasons.append(f"Furniture {obj['id']} has invalid geometry.")
        if not interior.buffer(5).covers(polygon):
            reasons.append(f"Furniture {obj['id']} leaves the approximate interior.")
        for zone_id, (zone_polygon, tolerance) in exclusion_zones.items():
            overlap = polygon.intersection(zone_polygon).area
            if overlap > tolerance:
                collision = f"{obj['id']} ↔ {zone_id} ({overlap:.1f}px²)"
                interior_wall_collisions.append(collision)
                reasons.append(f"Furniture enters a fixed excluded room: {collision}.")

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

    fixture_polygons = {
        fixture["id"]: fixed_fixture_polygon(fixture) for fixture in fixtures["fixtures"]
    }
    fixed_union = fixed_fixture_union(fixtures["fixtures"])
    fixed_fixture_blocked_by: dict[str, list[str]] = {}
    fixed_furnishing_blocked_by: dict[str, list[str]] = {}
    fixed_furnishing_polygons = {
        item["id"]: box(item["x"], item["y"], item["x"] + item["widthPx"], item["y"] + item["depthPx"])
        for item in (fixed_furnishings or {}).get("furnishings", [])
    }
    for obj in layout["objects"]:
        blockers = [
            fixture_id
            for fixture_id, fixture_polygon in fixture_polygons.items()
            if object_polygons[obj["id"]].intersection(fixture_polygon).area > 0.5
        ]
        if blockers:
            fixed_fixture_blocked_by[obj["id"]] = blockers
            for fixture_id in blockers:
                reasons.append(f"Furniture {obj['id']} overlaps fixed fixture {fixture_id}.")
        furnishing_blockers = [
            furnishing_id
            for furnishing_id, furnishing_polygon in fixed_furnishing_polygons.items()
            if object_polygons[obj["id"]].intersection(furnishing_polygon).area > 0.5
        ]
        if furnishing_blockers:
            fixed_furnishing_blocked_by[obj["id"]] = furnishing_blockers
            for furnishing_id in furnishing_blockers:
                reasons.append(f"Furniture {obj['id']} overlaps fixed furnishing {furnishing_id}.")

    desk = next(obj for obj in layout["objects"] if obj["type"] == "desk")
    desk_polygon = object_polygons[desk["id"]]
    desk_fixture_blocked_by = fixed_fixture_blocked_by.get(desk["id"], [])

    desk_fixture_clearance_cm = desk_polygon.distance(fixed_union) * cm_per_pixel
    if layout["selection"].get("deskPlacementId") == "lower-balcony-corner":
        minimum_passage_cm = constraints.get("lowerDeskKitchenPassageMinimumCm", 50)
        if desk_fixture_clearance_cm + 0.05 < minimum_passage_cm:
            reasons.append(
                f"Lower desk leaves only {desk_fixture_clearance_cm:.1f} cm to the fixed kitchen; "
                f"at least {minimum_passage_cm:g} cm is required."
            )

    work_zone_dimensions = constraints.get("deskWorkZoneCm", {"width": 60, "depth": 60})
    desk_work_zone = desk_work_zone_polygon(
        desk,
        cm_per_pixel,
        work_zone_dimensions.get("width", 60),
        work_zone_dimensions.get("depth", 60),
    )
    desk_work_zone_blocked_by: list[str] = []
    if desk_work_zone.is_empty:
        desk_work_zone_blocked_by.append("desk-cutout")
        reasons.append("Desk cutout is too small for the required chair/work zone.")
    else:
        if not interior.buffer(0.01).covers(desk_work_zone):
            desk_work_zone_blocked_by.append("interior-boundary")
            reasons.append("Desk chair/work zone leaves the approximate interior.")
        for fixture_id, fixture_polygon in fixture_polygons.items():
            if desk_work_zone.intersection(fixture_polygon).area > 0.5:
                desk_work_zone_blocked_by.append(fixture_id)
                reasons.append(f"Desk chair/work zone is blocked by fixed fixture {fixture_id}.")
        for other in (obj for obj in layout["objects"] if obj["id"] != desk["id"]):
            if desk_work_zone.intersection(object_polygons[other["id"]]).area > 0.5:
                desk_work_zone_blocked_by.append(other["id"])
                reasons.append(f"Desk chair/work zone is blocked by {other['id']}.")

    wardrobe_access_blocked_by: list[str] = []
    wardrobe_access_depth_cm = layout.get("selection", {}).get(
        "paxAccessDepthCm", constraints.get("wardrobeAccessDepthCm", 45)
    )
    for wardrobe in (obj for obj in layout["objects"] if obj["type"] == "wardrobe"):
        maximum_width_cm = layout.get("paxWallSegmentMaximumCm")
        if maximum_width_cm is not None and wardrobe["dimensionsCm"]["width"] > maximum_width_cm + 0.01:
            reasons.append(
                f"Wardrobe {wardrobe['id']} exceeds the {maximum_width_cm:g} cm fixed balcony-wall segment."
            )
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

    appliance_access_blocked_by: list[str] = []
    appliance_interior_wall_blocked_by: list[str] = []
    for appliance in (
        obj for obj in layout["objects"] if obj["type"] == "appliance" and obj.get("accessLabel")
    ):
        footprint = object_polygons[appliance["id"]]
        if not interior.covers(footprint):
            appliance_access_blocked_by.append("interior-boundary")
            reasons.append(f"Appliance {appliance['id']} leaves the apartment interior.")
        for wall in (item for item in apartment["walls"] if item["kind"] == "interior"):
            wall_polygon = LineString([wall["start"], wall["end"]]).buffer(
                wall["thicknessPx"] / 2, cap_style=2, join_style=2
            )
            if footprint.intersection(wall_polygon).area > 0.5:
                appliance_interior_wall_blocked_by.append(wall["id"])
                reasons.append(f"Appliance {appliance['id']} overlaps interior wall {wall['id']}.")

        access_zone = wardrobe_access_polygon(
            appliance,
            cm_per_pixel,
            appliance.get("accessDepthCm", constraints.get("applianceAccessDepthCm", 40)),
        )
        if not interior.covers(access_zone):
            appliance_access_blocked_by.append("interior-boundary")
            reasons.append(f"Appliance access for {appliance['id']} leaves the apartment interior.")
        for zone_id, (zone_polygon, tolerance) in exclusion_zones.items():
            if access_zone.intersection(zone_polygon).area > tolerance:
                appliance_access_blocked_by.append(zone_id)
                reasons.append(f"Appliance access for {appliance['id']} enters {zone_id}.")
        for fixture_id, fixture_polygon in fixture_polygons.items():
            if access_zone.intersection(fixture_polygon).area > 0.5:
                appliance_access_blocked_by.append(fixture_id)
                reasons.append(f"Appliance access for {appliance['id']} is blocked by fixed fixture {fixture_id}.")
        for other in (obj for obj in layout["objects"] if obj["id"] != appliance["id"]):
            if access_zone.intersection(object_polygons[other["id"]]).area > 0.5:
                appliance_access_blocked_by.append(other["id"])
                reasons.append(f"Appliance access for {appliance['id']} is blocked by {other['id']}.")
        for door in apartment["doors"]:
            if access_zone.intersection(door_swing_polygon(door)).area > 0.5:
                opening_fraction, _ = door_opening_fraction(door, {appliance["id"]: footprint})
                minimum_fraction = constraints["doorPolicies"].get("minimumOpeningFractionByDoor", {}).get(door["id"], 1.0)
                if opening_fraction + 0.01 >= minimum_fraction:
                    continue
                appliance_access_blocked_by.append(door["id"])
                reasons.append(f"Appliance access for {appliance['id']} conflicts with {door['id']}.")

    blocked_by: dict[str, list[str]] = {}
    door_opening_fractions: dict[str, float] = {}
    door_opening_limited_by: dict[str, list[str]] = {}
    minimum_opening_fractions = constraints["doorPolicies"].get("minimumOpeningFractionByDoor", {})
    for door in apartment["doors"]:
        opening_fraction, blockers = door_opening_fraction(door, object_polygons)
        door_id = door["id"]
        minimum_fraction = minimum_opening_fractions.get(door_id, 1.0)
        door_opening_fractions[door_id] = round(opening_fraction, 2)
        if blockers:
            door_opening_limited_by[door_id] = blockers
        if opening_fraction + 1e-9 < minimum_fraction:
            blocked_by[door_id] = blockers
            appliance_blockers = [
                obj_id for obj_id in blockers if objects_by_id[obj_id]["type"] == "appliance"
            ]
            if appliance_blockers:
                reasons.append(
                    f"Door {door_id} cannot reach its minimum opening because of appliance {', '.join(appliance_blockers)}."
                )

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
        "doorOpeningFractions": door_opening_fractions,
        "doorOpeningLimitedBy": door_opening_limited_by,
        "wardrobeAccessBlockedBy": wardrobe_access_blocked_by,
        "wardrobeAccessDepthCm": wardrobe_access_depth_cm,
        "storageAccessBlockedBy": storage_access_blocked_by,
        "applianceAccessBlockedBy": sorted(set(appliance_access_blocked_by)),
        "applianceInteriorWallBlockedBy": sorted(set(appliance_interior_wall_blocked_by)),
        "fixedFixtureBlockedBy": fixed_fixture_blocked_by,
        "fixedFurnishingBlockedBy": fixed_furnishing_blocked_by,
        "deskFixedFixtureBlockedBy": desk_fixture_blocked_by,
        "deskWorkZoneBlockedBy": desk_work_zone_blocked_by,
        "deskFixedFixtureClearanceCm": round(desk_fixture_clearance_cm, 1),
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
