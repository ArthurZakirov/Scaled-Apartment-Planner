from __future__ import annotations

import json
import math
import sys
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from furniture import resolve_scenario_data  # noqa: E402
from geometry import expand_apartment_geometry  # noqa: E402
from validate_geometry import evaluate_layout  # noqa: E402
from scenario_metrics import furniture_polygon  # noqa: E402


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

    def test_matrix_contains_72_unique_scenarios(self):
        ids = [scenario["id"] for scenario in self.scenario_data["scenarios"]]
        self.assertEqual(len(ids), 72)
        self.assertEqual(len(set(ids)), 72)

    def test_external_product_dimensions_are_resolved(self):
        layout = next(
            layout
            for layout in self.furniture["layouts"]
            if layout["selection"]["bedVariantId"] == "malm-140"
            and layout["selection"]["paxVariantId"] == "pax-200"
        )
        bed = next(obj for obj in layout["objects"] if obj["type"] == "bed")
        pax = next(obj for obj in layout["objects"] if obj["type"] == "wardrobe")
        self.assertEqual(bed["dimensionsCm"]["width"], 156)
        self.assertEqual(bed["dimensionsCm"]["depth"], 209)
        self.assertEqual(pax["dimensionsCm"]["width"], 199.6)
        self.assertTrue(pax["requiresAnchoring"])

    def test_current_bed_is_a_separate_product_with_user_dimensions(self):
        layout = next(
            layout for layout in self.furniture["layouts"]
            if layout["selection"]["arrangementId"] == "divider"
            and layout["selection"]["bedVariantId"] == "current-bed-90"
            and layout["selection"]["paxVariantId"] == "pax-200"
            and layout["selection"]["deskVariantId"] == "stable-180-150"
        )
        bed = next(obj for obj in layout["objects"] if obj["type"] == "bed")
        self.assertEqual(bed["templateId"], "current-bed")
        self.assertEqual(bed["dimensionsCm"], {"width": 111, "depth": 204})
        self.assertEqual(bed["mattressCm"], {"width": 90, "depth": 200})
        self.assertEqual(bed["confidence"], "user_provided_dimensions")

    def test_owned_bedside_cabinet_follows_every_bed(self):
        cm_per_pixel = self.apartment["scale"]["cmPerPixel"]
        for layout in self.furniture["layouts"]:
            bed = next(obj for obj in layout["objects"] if obj["type"] == "bed")
            cabinet = next(obj for obj in layout["objects"] if obj["type"] == "storage")
            self.assertEqual(cabinet["dimensionsCm"], {"width": 57.5, "depth": 43, "height": 54})
            self.assertAlmostEqual(
                furniture_polygon(bed, cm_per_pixel).distance(furniture_polygon(cabinet, cm_per_pixel)) * cm_per_pixel,
                2,
                places=1,
            )
            self.assertAlmostEqual((cabinet["positionPx"]["rotationDeg"] - bed["positionPx"]["rotationDeg"]) % 180, 90)

    def test_bed_wall_side_stays_fixed_across_width_variants(self):
        cm_per_pixel = self.apartment["scale"]["cmPerPixel"]
        wall_side_positions = []
        for layout in self.furniture["layouts"]:
            if layout["selection"]["arrangementId"] != "divider" or layout["selection"]["paxVariantId"] != "pax-200" or layout["selection"]["deskVariantId"] != "stable-180-150":
                continue
            bed = next(obj for obj in layout["objects"] if obj["type"] == "bed")
            angle = math.radians(bed["positionPx"]["rotationDeg"])
            axis = (math.cos(angle), math.sin(angle))
            center = bed["positionPx"]["center"]
            wall_side_positions.append(
                center[0] * axis[0] + center[1] * axis[1] - bed["dimensionsCm"]["width"] / cm_per_pixel / 2
            )
        self.assertEqual(len(wall_side_positions), 4)
        self.assertLess(max(wall_side_positions) - min(wall_side_positions), 0.001)

    def test_pax_bath_end_and_cross_axis_stay_fixed_across_width_variants(self):
        cm_per_pixel = self.apartment["scale"]["cmPerPixel"]
        bath_end_positions = []
        cross_axis_positions = []
        for layout in self.furniture["layouts"]:
            if layout["selection"]["arrangementId"] != "divider" or layout["selection"]["bedVariantId"] != "malm-140" or layout["selection"]["deskVariantId"] != "stable-180-150":
                continue
            pax = next(obj for obj in layout["objects"] if obj["type"] == "wardrobe")
            angle = math.radians(pax["positionPx"]["rotationDeg"])
            long_axis = (math.cos(angle), math.sin(angle))
            cross_axis = (-long_axis[1], long_axis[0])
            center = pax["positionPx"]["center"]
            bath_end_positions.append(
                center[0] * long_axis[0] + center[1] * long_axis[1] - pax["dimensionsCm"]["width"] / cm_per_pixel / 2
            )
            cross_axis_positions.append(center[0] * cross_axis[0] + center[1] * cross_axis[1])
        self.assertEqual(len(bath_end_positions), 3)
        self.assertLess(max(bath_end_positions) - min(bath_end_positions), 0.001)
        self.assertLess(max(cross_axis_positions) - min(cross_axis_positions), 0.001)

    def test_desk_top_and_right_edges_touch_same_walls_for_every_size(self):
        cm_per_pixel = self.apartment["scale"]["cmPerPixel"]
        anchors = []
        for layout in self.furniture["layouts"]:
            if layout["selection"]["arrangementId"] != "divider" or layout["selection"]["bedVariantId"] != "malm-140" or layout["selection"]["paxVariantId"] != "pax-200":
                continue
            desk = next(obj for obj in layout["objects"] if obj["type"] == "desk")
            polygon = furniture_polygon(desk, cm_per_pixel)
            anchors.append((polygon.bounds[2], polygon.bounds[1]))
        self.assertEqual(len(anchors), 4)
        self.assertLess(max(anchor[0] for anchor in anchors) - min(anchor[0] for anchor in anchors), 0.001)
        self.assertLess(max(anchor[1] for anchor in anchors) - min(anchor[1] for anchor in anchors), 0.001)

    def test_bed_to_pax_gap_grows_as_bed_gets_narrower(self):
        cm_per_pixel = self.apartment["scale"]["cmPerPixel"]
        signed_gaps = {}
        for layout in self.furniture["layouts"]:
            if layout["selection"]["arrangementId"] != "divider" or layout["selection"]["paxVariantId"] != "pax-200" or layout["selection"]["deskVariantId"] != "stable-180-150":
                continue
            bed = next(obj for obj in layout["objects"] if obj["type"] == "bed")
            pax = next(obj for obj in layout["objects"] if obj["type"] == "wardrobe")
            angle = math.radians(bed["positionPx"]["rotationDeg"])
            inward_axis = (math.cos(angle), math.sin(angle))
            bed_projection = [x * inward_axis[0] + y * inward_axis[1] for x, y in furniture_polygon(bed, cm_per_pixel).exterior.coords]
            pax_projection = [x * inward_axis[0] + y * inward_axis[1] for x, y in furniture_polygon(pax, cm_per_pixel).exterior.coords]
            signed_gaps[layout["selection"]["bedVariantId"]] = min(pax_projection) - max(bed_projection)
        self.assertGreater(signed_gaps["malm-140"], signed_gaps["malm-160"])
        self.assertGreater(signed_gaps["malm-160"], signed_gaps["malm-180"])

    def test_pax_height_does_not_create_duplicate_2d_variants(self):
        pax_objects = [
            obj
            for layout in self.furniture["layouts"]
            for obj in layout["objects"]
            if obj["type"] == "wardrobe"
        ]
        self.assertEqual({obj["variantId"] for obj in pax_objects}, {"pax-150", "pax-175", "pax-200"})
        self.assertTrue(all("height" not in obj["dimensionsCm"] for obj in pax_objects))
        self.assertTrue(all(obj["requiresAnchoring"] for obj in pax_objects))

    def test_wall_aligned_arrangements_are_geometrically_valid(self):
        results = {
            result["arrangementId"]: result
            for layout in self.furniture["layouts"]
            if layout["selection"]["paxVariantId"] == "pax-200"
            and layout["selection"]["deskVariantId"] == "stable-160-140"
            and layout["selection"]["arrangementId"] != "divider"
            for result in [evaluate_layout(layout, self.apartment, self.constraints)]
        }
        self.assertEqual(set(results), {"bath-wall-bed-shifted", "bath-wall-both-rotated"})
        self.assertTrue(all(result["valid"] for result in results.values()))
        self.assertTrue(all(result["installationStatus"] == "manufacturer_wall_mount_candidate" for result in results.values()))
        self.assertLess(results["bath-wall-bed-shifted"]["bedPaxGapCm"], 10)
        self.assertGreater(results["bath-wall-both-rotated"]["bedPaxGapCm"], 45)
        self.assertGreater(
            results["bath-wall-both-rotated"]["bedPaxGapCm"],
            results["bath-wall-bed-shifted"]["bedPaxGapCm"],
        )

    def test_every_valid_scenario_keeps_at_least_one_loggia_door_usable(self):
        for layout in self.furniture["layouts"]:
            result = evaluate_layout(layout, self.apartment, self.constraints)
            if result["valid"]:
                self.assertGreaterEqual(result["usableLoggiaDoors"], 1, layout["id"])

    def test_blocking_both_loggia_doors_is_always_invalid(self):
        layout = deepcopy(next(item for item in self.furniture["layouts"] if item["id"] == self.furniture["activeLayoutId"]))
        for door_id in ("door-loggia-bedroom", "door-loggia-living"):
            door = next(item for item in self.apartment["doors"] if item["id"] == door_id)
            layout["objects"].append(
                {
                    "id": f"test-blocker-{door_id}",
                    "type": "storage",
                    "dimensionsCm": {"width": 20, "depth": 20, "height": 20},
                    "positionPx": {"center": door["hinge"], "rotationDeg": 0},
                    "render": {"shape": "rectangle", "label": "Test blocker"},
                }
            )
        result = evaluate_layout(layout, self.apartment, self.constraints)
        self.assertFalse(result["valid"])
        self.assertIn("At least one Loggia door must remain usable.", result["reasons"])

    def test_generated_evaluations_match_geometric_results(self):
        results = [evaluate_layout(layout, self.apartment, self.constraints) for layout in self.furniture["layouts"]]
        evaluations = load_json("data/scenario-evaluations.json")
        self.assertEqual(sum(result["valid"] for result in results), evaluations["validCount"])
        self.assertGreater(evaluations["validCount"], 0)
        active = next(result for result in results if result["id"] == self.furniture["activeLayoutId"])
        self.assertTrue(active["valid"])


if __name__ == "__main__":
    unittest.main()
