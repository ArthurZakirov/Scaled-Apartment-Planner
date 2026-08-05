"""Shared parametric geometry expansion and declarative geometry checks."""

from __future__ import annotations

import copy
import math
from typing import Any

from shapely.geometry import LineString, Point, Polygon, box


def _offset_normal(
    start: list[float], end: list[float], depth_px: float, offset_side: str
) -> tuple[float, float]:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = math.hypot(dx, dy)
    if not math.isfinite(length) or length == 0:
        raise ValueError("Parametric wall profile requires a non-zero baseline.")
    direction = -1 if offset_side == "left" else 1
    return direction * (-dy / length) * depth_px, direction * (dx / length) * depth_px


def derive_rectangular_wall_profile(profile: dict[str, Any]) -> dict[str, Any]:
    start = list(profile["baselineStart"])
    end = list(profile["baselineEnd"])
    offset_x, offset_y = _offset_normal(start, end, profile["depthPx"], profile.get("offsetSide", "right"))
    far_start = [start[0] + offset_x, start[1] + offset_y]
    far_end = [end[0] + offset_x, end[1] + offset_y]
    common = {"kind": profile["kind"], "derivedFrom": profile["id"]}
    wall_ids = profile["wallIds"]

    return {
        "niche": {
            "id": profile["nicheId"],
            "type": profile["nicheType"],
            "points": [start, end, far_end, far_start],
            "confidence": profile["confidence"],
            "note": profile["note"],
            "derivedFrom": profile["id"],
        },
        "walls": [
            {
                **common,
                "id": wall_ids["baseline"],
                "start": start,
                "end": end,
                "thicknessPx": profile["baselineThicknessPx"],
            },
            {
                **common,
                "id": wall_ids["endCap"],
                "start": end,
                "end": far_end,
                "thicknessPx": profile["wallThicknessPx"],
            },
            {
                **common,
                "id": wall_ids["farSide"],
                "start": far_end,
                "end": far_start,
                "thicknessPx": profile["wallThicknessPx"],
            },
        ],
    }


def expand_apartment_geometry(apartment: dict[str, Any]) -> dict[str, Any]:
    expanded = copy.deepcopy(apartment)
    expanded.setdefault("niches", [])
    for profile in expanded.get("wallProfiles", []):
        derived = derive_rectangular_wall_profile(profile)
        expanded["walls"].extend(derived["walls"])
        expanded["niches"].append(derived["niche"])
    return expanded


def _vector(wall: dict[str, Any]) -> tuple[float, float]:
    return wall["end"][0] - wall["start"][0], wall["end"][1] - wall["start"][1]


def _axis_angle_degrees(first: dict[str, Any], second: dict[str, Any]) -> float:
    ax, ay = _vector(first)
    bx, by = _vector(second)
    denominator = math.hypot(ax, ay) * math.hypot(bx, by)
    if denominator == 0:
        return math.nan
    cosine = max(-1.0, min(1.0, (ax * bx + ay * by) / denominator))
    directed = math.degrees(math.acos(cosine))
    return min(directed, 180.0 - directed)


def _endpoint(wall: dict[str, Any], endpoint: str) -> list[float]:
    if endpoint not in {"start", "end"}:
        raise ValueError(f"Unsupported wall endpoint: {endpoint}")
    return wall[endpoint]


def _wall_shape(wall: dict[str, Any]) -> Polygon:
    return LineString([wall["start"], wall["end"]]).buffer(
        wall["thicknessPx"] / 2, cap_style=2, join_style=2
    )


def _fixture_shape(fixture: dict[str, Any]) -> Polygon:
    return box(
        fixture["x"],
        fixture["y"],
        fixture["x"] + fixture["widthPx"],
        fixture["y"] + fixture["depthPx"],
    )


def validate_geometry_rules(
    apartment: dict[str, Any], fixtures: dict[str, Any], config: dict[str, Any]
) -> tuple[list[str], list[str]]:
    walls = {wall["id"]: wall for wall in apartment["walls"]}
    fixture_map = {fixture["id"]: fixture for fixture in fixtures["fixtures"]}
    errors: list[str] = []
    results: list[str] = []

    for rule in config["rules"]:
        rule_id = rule["id"]
        rule_type = rule["type"]
        tolerance = rule.get("tolerance", config["defaults"].get("distanceTolerancePx", 0.1))
        passed = False
        detail = ""

        try:
            if rule_type in {"parallel", "perpendicular"}:
                first, second = (walls[wall_id] for wall_id in rule["wallIds"])
                actual = _axis_angle_degrees(first, second)
                expected = 0.0 if rule_type == "parallel" else 90.0
                deviation = abs(actual - expected)
                passed = deviation <= tolerance
                detail = f"actual {actual:.3f}°, expected {expected:.1f}° ± {tolerance:.3f}°"
            elif rule_type == "shared_endpoint":
                first_ref, second_ref = rule["points"]
                first = _endpoint(walls[first_ref["wallId"]], first_ref["endpoint"])
                second = _endpoint(walls[second_ref["wallId"]], second_ref["endpoint"])
                actual = math.dist(first, second)
                passed = actual <= tolerance
                detail = f"gap {actual:.3f}px, maximum {tolerance:.3f}px"
            elif rule_type == "point_on_wall":
                point_ref = rule["point"]
                point = _endpoint(walls[point_ref["wallId"]], point_ref["endpoint"])
                target = walls[rule["targetWallId"]]
                actual = LineString([target["start"], target["end"]]).distance(Point(point))
                passed = actual <= tolerance
                detail = f"distance {actual:.3f}px, maximum {tolerance:.3f}px"
            elif rule_type == "wall_fixture_clearance":
                wall = walls[rule["wallId"]]
                fixture = fixture_map[rule["fixtureId"]]
                actual = _wall_shape(wall).distance(_fixture_shape(fixture))
                minimum = rule["minimumPx"]
                passed = actual + tolerance >= minimum
                detail = f"clearance {actual:.3f}px, minimum {minimum:.3f}px"
            else:
                raise ValueError(f"Unsupported geometry rule type: {rule_type}")
        except KeyError as exc:
            detail = f"missing referenced geometry: {exc}"

        status = "PASS" if passed else "FAIL"
        results.append(f"{status} {rule_id}: {detail}")
        if not passed:
            errors.append(f"Geometry rule {rule_id} failed: {detail}")

    return errors, results
