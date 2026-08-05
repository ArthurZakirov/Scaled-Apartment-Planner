from __future__ import annotations

import json
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from furniture import resolve_scenario_data  # noqa: E402
from geometry import expand_apartment_geometry  # noqa: E402
from validate_geometry import evaluate_layout  # noqa: E402


def load_json(relative: str):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


class ScenarioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = load_json("data/furniture-catalog.json")
        cls.scenario_data = load_json("data/layout-scenarios.json")
        cls.furniture = resolve_scenario_data(cls.scenario_data, cls.catalog)
        cls.apartment = expand_apartment_geometry(load_json("data/apartment.json"))
        cls.constraints = load_json("data/layout-constraints.json")

    def test_matrix_contains_36_unique_scenarios(self):
        ids = [scenario["id"] for scenario in self.scenario_data["scenarios"]]
        self.assertEqual(len(ids), 36)
        self.assertEqual(len(set(ids)), 36)

    def test_external_product_dimensions_are_resolved(self):
        active = next(layout for layout in self.furniture["layouts"] if layout["id"] == self.furniture["activeLayoutId"])
        bed = next(obj for obj in active["objects"] if obj["type"] == "bed")
        pax = next(obj for obj in active["objects"] if obj["type"] == "wardrobe")
        self.assertEqual(bed["dimensionsCm"]["width"], 156)
        self.assertEqual(bed["dimensionsCm"]["depth"], 209)
        self.assertEqual(pax["dimensionsCm"]["width"], 199.6)
        self.assertTrue(pax["requiresAnchoring"])

    def test_bed_wall_side_stays_fixed_across_width_variants(self):
        cm_per_pixel = self.apartment["scale"]["cmPerPixel"]
        wall_side_positions = []
        for layout in self.furniture["layouts"]:
            if layout["selection"]["paxVariantId"] != "pax-200" or layout["selection"]["deskVariantId"] != "stable-180-150":
                continue
            bed = next(obj for obj in layout["objects"] if obj["type"] == "bed")
            angle = math.radians(bed["positionPx"]["rotationDeg"])
            axis = (math.cos(angle), math.sin(angle))
            center = bed["positionPx"]["center"]
            wall_side_positions.append(
                center[0] * axis[0] + center[1] * axis[1] - bed["dimensionsCm"]["width"] / cm_per_pixel / 2
            )
        self.assertEqual(len(wall_side_positions), 3)
        self.assertLess(max(wall_side_positions) - min(wall_side_positions), 0.001)

    def test_expected_number_of_scenarios_are_geometrically_valid(self):
        results = [evaluate_layout(layout, self.apartment, self.constraints) for layout in self.furniture["layouts"]]
        self.assertEqual(sum(result["valid"] for result in results), 12)
        active = next(result for result in results if result["id"] == self.furniture["activeLayoutId"])
        self.assertTrue(active["valid"])


if __name__ == "__main__":
    unittest.main()
