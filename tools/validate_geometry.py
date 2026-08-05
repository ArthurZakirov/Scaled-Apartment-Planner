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
    from shapely.geometry import LineString, Point, Polygon
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Install dependencies first: python3 -m pip install -r requirements.txt") from exc

from geometry import expand_apartment_geometry, validate_geometry_rules
from furniture import resolve_scenario_data
from scenario_metrics import evaluate_layout, rank_results

ROOT = Path(__file__).resolve().parents[1]


def load_json(relative: str) -> dict[str, Any]:
    with (ROOT / relative).open(encoding="utf-8") as handle:
        return json.load(handle)


def main() -> int:
    apartment_source = load_json("data/apartment.json")
    apartment = expand_apartment_geometry(apartment_source)
    fixtures = load_json("data/fixed-fixtures.json")
    catalog = load_json("data/furniture-catalog.json")
    scenario_data = load_json("data/layout-scenarios.json")
    scenario_evaluations = load_json("data/scenario-evaluations.json")
    furniture = resolve_scenario_data(scenario_data, catalog)
    constraints = load_json("data/layout-constraints.json")
    geometry_rules = load_json("data/geometry-rules.json")

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

    wall_ids = [wall["id"] for wall in apartment["walls"]]
    if len(wall_ids) != len(set(wall_ids)):
        errors.append("Wall IDs are not unique after parametric geometry expansion.")

    for wall in apartment["walls"]:
        if wall["start"] == wall["end"]:
            errors.append(f"Wall {wall['id']} has zero length.")
        if not all(math.isfinite(value) for point in (wall["start"], wall["end"]) for value in point):
            errors.append(f"Wall {wall['id']} contains non-finite coordinates.")
        if wall["thicknessPx"] <= 0:
            errors.append(f"Wall {wall['id']} has a non-positive thickness.")
        line = LineString([wall["start"], wall["end"]])
        if not view_polygon.buffer(1).covers(line):
            errors.append(f"Wall {wall['id']} leaves the configured viewBox.")

    geometry_errors, geometry_results = validate_geometry_rules(apartment, fixtures, geometry_rules)
    errors.extend(geometry_errors)

    door_ids = [door["id"] for door in apartment["doors"]]
    if len(door_ids) != len(set(door_ids)):
        errors.append("Door IDs are not unique.")

    if scenario_data.get("scenarioCount") != len(scenario_data["scenarios"]):
        errors.append("Scenario count does not match the generated scenario list.")
    if len(scenario_data["scenarios"]) != 36:
        errors.append(f"Expected the 3 × 3 × 4 matrix to contain 36 scenarios, found {len(scenario_data['scenarios'])}.")

    scenario_results = [evaluate_layout(layout, apartment, constraints) for layout in furniture["layouts"]]
    valid_scenarios = rank_results(scenario_results)
    expected_evaluations = {
        "version": 1,
        "scenarioCount": len(scenario_results),
        "validCount": len(valid_scenarios),
        "rankedValidScenarioIds": [result["id"] for result in valid_scenarios],
        "results": scenario_results,
    }
    if scenario_evaluations != expected_evaluations:
        errors.append("Scenario evaluations are stale; run npm run generate:scenarios.")
    if not valid_scenarios:
        errors.append("No generated furniture scenario satisfies the mandatory constraints.")

    active_layout = next((item for item in furniture["layouts"] if item["id"] == furniture["activeLayoutId"]), None)
    if active_layout is None:
        errors.append("Active layout does not exist.")
        return finish(errors, warnings, geometry_results=geometry_results, scenario_results=scenario_results)

    active_result = next(result for result in scenario_results if result["id"] == active_layout["id"])
    errors.extend(active_result["reasons"])
    blocked_door_ids = set(active_result["blockedBy"])
    for obj in active_layout["objects"]:
        if obj.get("requiresAnchoring"):
            warnings.append(f"{obj['render']['label']} requires a verified anchoring solution before installation.")

    if apartment["scale"]["status"] != "confirmed":
        warnings.append("Entrance-door anchor is confirmed, but real-world clearances remain estimates because the source is not to scale.")

    return finish(errors, warnings, active_layout["id"], blocked_door_ids, geometry_results, scenario_results)


def finish(
    errors: list[str],
    warnings: list[str],
    layout_id: str | None = None,
    blocked: set[str] | None = None,
    geometry_results: list[str] | None = None,
    scenario_results: list[dict[str, Any]] | None = None,
) -> int:
    print("Scaled Apartment Planner validation")
    if layout_id:
        print(f"  layout: {layout_id}")
    if blocked is not None:
        print(f"  blocked doors: {', '.join(sorted(blocked)) or 'none'}")
    if geometry_results:
        print("  geometry rules:")
        for result in geometry_results:
            print(f"    {result}")
    if scenario_results:
        valid = sorted(
            (result for result in scenario_results if result["valid"]),
            key=lambda result: result["score"],
            reverse=True,
        )
        print(f"  scenarios: {len(valid)}/{len(scenario_results)} valid")
        for result in valid[:3]:
            gap = result["minimumFurnitureGapCm"]
            print(f"    score {result['score']:.1f} · gap {gap:.1f} cm · {result['name']}")
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
