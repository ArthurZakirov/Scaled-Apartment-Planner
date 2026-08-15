#!/usr/bin/env python3
"""Generate browser-readable metrics for every furniture scenario."""

from __future__ import annotations

import json
from pathlib import Path

from furniture import resolve_scenario_data
from geometry import expand_apartment_geometry
from scenario_metrics import evaluate_layout, rank_results

ROOT = Path(__file__).resolve().parents[1]


def load_json(relative: str) -> dict:
    with (ROOT / relative).open(encoding="utf-8") as handle:
        return json.load(handle)


def main() -> None:
    apartment = expand_apartment_geometry(load_json("data/apartment.json"))
    catalog = load_json("data/furniture-catalog.json")
    scenarios = load_json("data/layout-scenarios.json")
    constraints = load_json("data/layout-constraints.json")
    fixtures = load_json("data/fixed-fixtures.json")
    fixed_furnishings = load_json("data/fixed-furnishings.json")
    furniture = resolve_scenario_data(scenarios, catalog)
    results = [
        evaluate_layout(layout, apartment, constraints, fixtures, fixed_furnishings) for layout in furniture["layouts"]
    ]
    ranked = rank_results(results)
    payload = {
        "version": 1,
        "scenarioCount": len(results),
        "validCount": len(ranked),
        "rankedValidScenarioIds": [result["id"] for result in ranked],
        "results": results,
    }
    output = ROOT / "data/scenario-evaluations.json"
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Generated {len(results)} evaluations ({len(ranked)} valid) in {output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
