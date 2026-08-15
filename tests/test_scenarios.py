from __future__ import annotations

import json
import math
import sys
import unittest
from copy import deepcopy
from pathlib import Path

from shapely.geometry import LineString, Polygon

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from furniture import resolve_scenario_data  # noqa: E402
from geometry import expand_apartment_geometry  # noqa: E402
from validate_geometry import evaluate_layout  # noqa: E402
from desk_geometry import desk_work_zone_polygon, fixed_fixture_polygon, fixed_fixture_union  # noqa: E402
from scenario_metrics import furniture_polygon, wardrobe_access_polygon  # noqa: E402


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
        cls.fixtures = load_json("data/fixed-fixtures.json")

    def evaluate(self, layout):
        return evaluate_layout(layout, self.apartment, self.constraints, self.fixtures)

    def test_matrix_contains_5760_unique_scenarios(self):
        ids = [scenario["id"] for scenario in self.scenario_data["scenarios"]]
        self.assertEqual(len(ids), 5760)
        self.assertEqual(len(set(ids)), 5760)

    def test_pax_access_is_an_independent_axis_with_stable_legacy_urls(self):
        grouped = {}
        for layout in self.furniture["layouts"]:
            selection = layout["selection"]
            key = (
                selection["arrangementId"],
                selection["bedVariantId"],
                selection["paxVariantId"],
                selection["deskVariantId"],
                selection["deskPlacementId"],
                selection["minifridgePlacementId"],
            )
            grouped.setdefault(key, {})[selection["paxAccessDepthCm"]] = layout["id"]
        self.assertTrue(grouped)
        for variants in grouped.values():
            self.assertEqual(set(variants), {0, 30, 45, 60})
            self.assertNotIn("pax-access", variants[45])
            for depth in (0, 30, 60):
                self.assertIn(f"-pax-access-{depth}", variants[depth])

    def test_minifridge_placement_is_independent_and_keeps_other_axes_fixed(self):
        grouped = {}
        for layout in self.furniture["layouts"]:
            selection = layout["selection"]
            key = tuple(
                selection[name]
                for name in (
                    "arrangementId",
                    "bedVariantId",
                    "paxVariantId",
                    "paxAccessDepthCm",
                    "deskVariantId",
                    "deskPlacementId",
                )
            )
            grouped.setdefault(key, set()).add(selection["minifridgePlacementId"])
        self.assertTrue(grouped)
        self.assertTrue(
            all(placements == {"endcap-extension", "kitchen-back-wall"} for placements in grouped.values())
        )

    def test_minifridge_footprint_and_door_zone_are_clear_in_every_valid_scenario(self):
        interior = Polygon(next(space["points"] for space in self.apartment["spaces"] if space["id"] == "space-main"))
        fixture_polygons = [fixed_fixture_polygon(item) for item in self.fixtures["fixtures"]]
        for layout in self.furniture["layouts"]:
            result = self.evaluate(layout)
            if not result["valid"]:
                continue
            fridge = next(obj for obj in layout["objects"] if obj["type"] == "appliance")
            footprint = furniture_polygon(fridge, self.apartment["scale"]["cmPerPixel"])
            access = wardrobe_access_polygon(fridge, self.apartment["scale"]["cmPerPixel"], 40)
            self.assertTrue(interior.covers(footprint), layout["id"])
            self.assertTrue(interior.covers(access), layout["id"])
            self.assertTrue(all(footprint.intersection(item).area <= 0.5 for item in fixture_polygons), layout["id"])
            self.assertTrue(all(access.intersection(item).area <= 0.5 for item in fixture_polygons), layout["id"])
            self.assertEqual(result["applianceAccessBlockedBy"], [], layout["id"])
            self.assertEqual(result["applianceInteriorWallBlockedBy"], [], layout["id"])

    def test_southeast_interior_contour_preserves_original_wall_step(self):
        main_points = next(space["points"] for space in self.apartment["spaces"] if space["id"] == "space-main")
        self.assertIn([[507, 263], [507, 514], [493, 514], [493, 527]], [main_points[index:index + 4] for index in range(len(main_points) - 3)])
        walls = {wall["id"]: wall for wall in self.apartment["walls"]}
        self.assertEqual(walls["wall-east-lower"]["end"], [521, 526])
        self.assertEqual(walls["wall-southeast-zig-horizontal"]["end"], [505, 526])
        self.assertEqual(walls["wall-southeast-zig-vertical"]["end"], [505, 539])

    def test_estimated_new_bed_dimensions_are_resolved(self):
        layout = next(
            layout
            for layout in self.furniture["layouts"]
            if layout["selection"]["bedVariantId"] == "new-bed-140"
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

    def test_owned_bedside_cabinet_follows_bed_outside_fixed_corner_layout(self):
        cm_per_pixel = self.apartment["scale"]["cmPerPixel"]
        for layout in self.furniture["layouts"]:
            bed = next(obj for obj in layout["objects"] if obj["type"] == "bed")
            cabinet = next(obj for obj in layout["objects"] if obj["type"] == "storage")
            self.assertEqual(cabinet["dimensionsCm"], {"width": 43, "depth": 57.5, "height": 54})
            self.assertEqual(cabinet["accessLabel"], "Schubladen")
            if layout["selection"]["arrangementId"] == "divider":
                self.assertEqual(cabinet["positionPx"], {"center": [287, 163], "rotationDeg": 144})
                continue
            self.assertAlmostEqual(
                furniture_polygon(bed, cm_per_pixel).distance(furniture_polygon(cabinet, cm_per_pixel)) * cm_per_pixel,
                2,
                places=1,
            )
            expected_rotation_difference = (
                0
                if layout["selection"]["arrangementId"] in {"bath-wall-both-rotated", "east-wall-wardrobe", "kitchen-wall-wardrobe"}
                else 90
            )
            self.assertAlmostEqual(
                (cabinet["positionPx"]["rotationDeg"] - bed["positionPx"]["rotationDeg"]) % 180,
                expected_rotation_difference,
            )

    def test_divider_commode_stays_out_of_bathroom_walls(self):
        cm_per_pixel = self.apartment["scale"]["cmPerPixel"]
        bath_zone = Polygon(next(zone["points"] for zone in self.apartment["furnitureExclusionZones"] if zone["id"] == "space-bath"))
        for layout in self.furniture["layouts"]:
            if layout["selection"]["arrangementId"] != "divider":
                continue
            cabinet = next(obj for obj in layout["objects"] if obj["type"] == "storage")
            cabinet_polygon = furniture_polygon(cabinet, cm_per_pixel)
            self.assertLessEqual(cabinet_polygon.intersection(bath_zone).area, 25, layout["id"])

    def test_divider_commode_remains_next_to_90_cm_beds_with_clear_drawers(self):
        cm_per_pixel = self.apartment["scale"]["cmPerPixel"]
        for bed_variant_id in ("current-bed-90", "new-bed-90"):
            layout = next(
                item
                for item in self.furniture["layouts"]
                if item["selection"]["arrangementId"] == "divider"
                and item["selection"]["bedVariantId"] == bed_variant_id
            )
            bed = next(obj for obj in layout["objects"] if obj["type"] == "bed")
            cabinet = next(obj for obj in layout["objects"] if obj["type"] == "storage")
            self.assertLessEqual(
                furniture_polygon(bed, cm_per_pixel).distance(furniture_polygon(cabinet, cm_per_pixel)) * cm_per_pixel,
                5,
            )
            self.assertNotIn("sleeping-bed", self.evaluate(layout)["storageAccessBlockedBy"])

    def test_every_valid_scenario_stays_on_the_furniture_side_of_interior_walls(self):
        for layout in self.furniture["layouts"]:
            result = self.evaluate(layout)
            if result["valid"]:
                self.assertEqual(result["interiorWallCollisions"], [], layout["id"])

    def test_furniture_placed_across_bath_wall_is_rejected(self):
        layout = deepcopy(next(item for item in self.furniture["layouts"] if item["id"] == self.furniture["activeLayoutId"]))
        cabinet = next(obj for obj in layout["objects"] if obj["type"] == "storage")
        bath_wall = next(wall for wall in self.apartment["walls"] if wall["id"] == "wall-bath-lower")
        cabinet["positionPx"] = {
            "center": [
                (bath_wall["start"][0] + bath_wall["end"][0]) / 2,
                (bath_wall["start"][1] + bath_wall["end"][1]) / 2,
            ],
            "rotationDeg": 0,
        }
        result = self.evaluate(layout)
        self.assertFalse(result["valid"])
        self.assertTrue(
            any("owned-bedside-cabinet ↔ space-bath" in collision for collision in result["interiorWallCollisions"])
        )

    def test_bed_wall_side_stays_fixed_across_width_variants(self):
        cm_per_pixel = self.apartment["scale"]["cmPerPixel"]
        wall_side_positions = []
        for layout in self.furniture["layouts"]:
            if layout["selection"]["arrangementId"] != "divider" or layout["selection"]["paxVariantId"] != "pax-200" or layout["selection"]["deskVariantId"] != "stable-180-150" or layout["selection"]["deskPlacementId"] != "upper-loggia-corner" or layout["selection"]["paxAccessDepthCm"] != 45 or layout["selection"]["minifridgePlacementId"] != "endcap-extension":
                continue
            bed = next(obj for obj in layout["objects"] if obj["type"] == "bed")
            angle = math.radians(bed["positionPx"]["rotationDeg"])
            axis = (math.cos(angle), math.sin(angle))
            center = bed["positionPx"]["center"]
            wall_side_positions.append(
                center[0] * axis[0] + center[1] * axis[1] - bed["dimensionsCm"]["width"] / cm_per_pixel / 2
            )
        self.assertEqual(len(wall_side_positions), 6)
        self.assertLess(max(wall_side_positions) - min(wall_side_positions), 0.001)

    def test_pax_bath_end_and_cross_axis_stay_fixed_across_width_variants(self):
        cm_per_pixel = self.apartment["scale"]["cmPerPixel"]
        bath_end_positions = []
        cross_axis_positions = []
        for layout in self.furniture["layouts"]:
            if layout["selection"]["arrangementId"] != "divider" or layout["selection"]["bedVariantId"] != "new-bed-140" or layout["selection"]["deskVariantId"] != "stable-180-150" or layout["selection"]["deskPlacementId"] != "upper-loggia-corner" or layout["selection"]["paxAccessDepthCm"] != 45 or layout["selection"]["minifridgePlacementId"] != "endcap-extension":
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

    def test_each_desk_position_keeps_its_corner_anchor_for_every_size(self):
        cm_per_pixel = self.apartment["scale"]["cmPerPixel"]
        anchors = {"upper-loggia-corner": [], "lower-balcony-corner": []}
        for layout in self.furniture["layouts"]:
            if layout["selection"]["arrangementId"] != "divider" or layout["selection"]["bedVariantId"] != "new-bed-140" or layout["selection"]["paxVariantId"] != "pax-200" or layout["selection"]["paxAccessDepthCm"] != 45 or layout["selection"]["minifridgePlacementId"] != "endcap-extension":
                continue
            desk = next(obj for obj in layout["objects"] if obj["type"] == "desk")
            polygon = furniture_polygon(desk, cm_per_pixel)
            placement_id = layout["selection"]["deskPlacementId"]
            anchor = (polygon.bounds[2], polygon.bounds[1]) if placement_id == "upper-loggia-corner" else (polygon.bounds[2], polygon.bounds[3])
            anchors[placement_id].append(anchor)
        self.assertEqual({key: len(value) for key, value in anchors.items()}, {"upper-loggia-corner": 4, "lower-balcony-corner": 4})
        for values in anchors.values():
            self.assertLess(max(anchor[0] for anchor in values) - min(anchor[0] for anchor in values), 0.001)
            self.assertLess(max(anchor[1] for anchor in values) - min(anchor[1] for anchor in values), 0.001)
        self.assertAlmostEqual(anchors["upper-loggia-corner"][0][0], 510.4211, places=3)
        self.assertAlmostEqual(anchors["upper-loggia-corner"][0][1], 263, places=3)
        self.assertAlmostEqual(anchors["lower-balcony-corner"][0][0], 493, places=3)
        self.assertAlmostEqual(anchors["lower-balcony-corner"][0][1], 527, places=3)

    def test_lower_desk_runs_up_the_right_wall_and_opens_into_the_room(self):
        layout = next(
            item
            for item in self.furniture["layouts"]
            if item["selection"]["deskPlacementId"] == "lower-balcony-corner"
        )
        desk = next(obj for obj in layout["objects"] if obj["type"] == "desk")
        self.assertEqual(desk["positionPx"]["rotationDeg"], 90)
        self.assertEqual(desk["positionPx"]["handedness"], "right")

    def test_rotated_lower_desk_variants_keep_the_local_50_cm_kitchen_passage(self):
        expected_clearance = {
            "quick-150-150": 52.2,
            "stable-160-140": 62.2,
            "quick-180-150": 52.2,
            "stable-180-150": 52.2,
        }
        sampled = {}
        for layout in self.furniture["layouts"]:
            if (
                layout["selection"]["arrangementId"] != "divider"
                or layout["selection"]["bedVariantId"] != "new-bed-90"
                or layout["selection"]["paxVariantId"] != "pax-200"
                or layout["selection"]["deskPlacementId"] != "lower-balcony-corner"
                or layout["selection"]["paxAccessDepthCm"] != 45
            ):
                continue
            result = self.evaluate(layout)
            sampled[layout["selection"]["deskVariantId"]] = result["deskFixedFixtureClearanceCm"]
            passage_reasons = [reason for reason in result["reasons"] if "to the fixed kitchen" in reason]
            self.assertEqual(passage_reasons, [], layout["id"])
        self.assertEqual(set(sampled), set(expected_clearance))
        for variant_id, clearance in sampled.items():
            self.assertAlmostEqual(clearance, expected_clearance[variant_id], delta=0.2)

    def test_every_valid_desk_has_a_clear_60_by_60_cm_work_zone(self):
        cm_per_pixel = self.apartment["scale"]["cmPerPixel"]
        interior = next(space for space in self.apartment["spaces"] if space["id"] == "space-main")
        interior_polygon = Polygon(interior["points"])
        fixtures = fixed_fixture_union(self.fixtures["fixtures"])
        for layout in self.furniture["layouts"]:
            result = self.evaluate(layout)
            if not result["valid"]:
                continue
            desk = next(obj for obj in layout["objects"] if obj["type"] == "desk")
            zone = desk_work_zone_polygon(desk, cm_per_pixel, 60, 60)
            self.assertAlmostEqual(zone.area * cm_per_pixel**2, 3600, places=1, msg=layout["id"])
            self.assertTrue(interior_polygon.buffer(0.01).covers(zone), layout["id"])
            self.assertEqual(result["deskWorkZoneBlockedBy"], [], layout["id"])
            self.assertLess(zone.intersection(fixtures).area, 0.5, layout["id"])

    def test_desk_overlapping_a_fixed_kitchen_fixture_is_invalid(self):
        layout = deepcopy(next(item for item in self.furniture["layouts"] if item["id"] == self.furniture["activeLayoutId"]))
        desk = next(obj for obj in layout["objects"] if obj["type"] == "desk")
        desk["positionPx"]["topLeft"] = [205, 500]
        desk["positionPx"]["rotationDeg"] = 0
        desk["positionPx"]["handedness"] = "right"
        result = self.evaluate(layout)
        self.assertFalse(result["valid"])
        self.assertIn("kitchen-bottom-run", result["deskFixedFixtureBlockedBy"])

    def test_furniture_inside_the_desk_work_zone_is_invalid(self):
        layout = deepcopy(next(item for item in self.furniture["layouts"] if item["id"] == self.furniture["activeLayoutId"]))
        desk = next(obj for obj in layout["objects"] if obj["type"] == "desk")
        cabinet = next(obj for obj in layout["objects"] if obj["type"] == "storage")
        center = desk_work_zone_polygon(desk, self.apartment["scale"]["cmPerPixel"]).centroid
        cabinet["positionPx"] = {"center": [center.x, center.y], "rotationDeg": 0}
        result = self.evaluate(layout)
        self.assertFalse(result["valid"])
        self.assertIn(cabinet["id"], result["deskWorkZoneBlockedBy"])

    def test_bed_to_pax_gap_grows_as_bed_gets_narrower(self):
        cm_per_pixel = self.apartment["scale"]["cmPerPixel"]
        signed_gaps = {}
        for layout in self.furniture["layouts"]:
            if layout["selection"]["arrangementId"] != "divider" or layout["selection"]["paxVariantId"] != "pax-200" or layout["selection"]["deskVariantId"] != "stable-180-150" or layout["selection"]["deskPlacementId"] != "upper-loggia-corner" or layout["selection"]["paxAccessDepthCm"] != 45:
                continue
            bed = next(obj for obj in layout["objects"] if obj["type"] == "bed")
            pax = next(obj for obj in layout["objects"] if obj["type"] == "wardrobe")
            angle = math.radians(bed["positionPx"]["rotationDeg"])
            inward_axis = (math.cos(angle), math.sin(angle))
            bed_projection = [x * inward_axis[0] + y * inward_axis[1] for x, y in furniture_polygon(bed, cm_per_pixel).exterior.coords]
            pax_projection = [x * inward_axis[0] + y * inward_axis[1] for x, y in furniture_polygon(pax, cm_per_pixel).exterior.coords]
            signed_gaps[layout["selection"]["bedVariantId"]] = min(pax_projection) - max(bed_projection)
        self.assertGreater(signed_gaps["new-bed-90"], signed_gaps["new-bed-120"])
        self.assertGreater(signed_gaps["new-bed-120"], signed_gaps["new-bed-140"])
        self.assertGreater(signed_gaps["new-bed-140"], signed_gaps["new-bed-160"])
        self.assertGreater(signed_gaps["new-bed-160"], signed_gaps["new-bed-180"])

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

    def test_wall_aligned_arrangements_are_rejected_when_bed_or_boundary_blocks_use(self):
        results = {
            result["arrangementId"]: result
            for layout in self.furniture["layouts"]
            if layout["selection"]["paxVariantId"] == "pax-200"
            and layout["selection"]["deskVariantId"] == "stable-160-140"
            and layout["selection"]["deskPlacementId"] == "upper-loggia-corner"
            and layout["selection"]["bedVariantId"] == "current-bed-90"
            and layout["selection"]["arrangementId"] != "divider"
            and layout["selection"]["paxAccessDepthCm"] == 45
            for result in [self.evaluate(layout)]
        }
        self.assertEqual(set(results), {"bath-wall-bed-shifted", "bath-wall-both-rotated", "kitchen-wall-wardrobe"})
        self.assertTrue(all(result["installationStatus"] == "manufacturer_wall_mount_candidate" for result in results.values()))
        self.assertFalse(results["bath-wall-bed-shifted"]["valid"])
        self.assertTrue(any("leaves the approximate interior" in reason for reason in results["bath-wall-bed-shifted"]["reasons"]))
        self.assertFalse(results["bath-wall-both-rotated"]["valid"])
        self.assertIn("sleeping-bed", results["bath-wall-both-rotated"]["wardrobeAccessBlockedBy"])
        self.assertGreater(results["bath-wall-both-rotated"]["bedPaxGapCm"], 30)
        self.assertFalse(results["kitchen-wall-wardrobe"]["valid"])
        self.assertIn("exceeds the 167 cm fixed balcony-wall segment", " ".join(results["kitchen-wall-wardrobe"]["reasons"]))

    def test_both_rotated_120_with_lower_desk_clears_loggia_but_not_pax_access(self):
        layouts = [
            layout
            for layout in self.furniture["layouts"]
            if layout["selection"]["arrangementId"] == "bath-wall-both-rotated"
            and layout["selection"]["bedVariantId"] == "new-bed-120"
            and layout["selection"]["paxAccessDepthCm"] == 45
            and layout["selection"]["minifridgePlacementId"] == "endcap-extension"
            and layout["selection"]["deskPlacementId"] == "lower-balcony-corner"
        ]
        self.assertEqual(len(layouts), 12)
        for layout in layouts:
            result = self.evaluate(layout)
            self.assertFalse(result["valid"])
            self.assertGreaterEqual(result["usableLoggiaDoors"], 1)
            self.assertIn("sleeping-bed", result["wardrobeAccessBlockedBy"])

    def test_both_rotated_90_with_open_pax_keeps_commode_drawers_usable(self):
        layout = next(
            item
            for item in self.furniture["layouts"]
            if item["id"]
            == "scenario-bath-wall-both-rotated-new-bed-90-pax-150-quick-150-150-lower-balcony-corner-pax-access-0-fridge-kitchen-back-wall"
        )
        result = self.evaluate(layout)
        cabinet = next(obj for obj in layout["objects"] if obj["id"] == "owned-bedside-cabinet")
        bed = next(obj for obj in layout["objects"] if obj["id"] == "sleeping-bed")

        self.assertTrue(result["valid"], result["reasons"])
        self.assertEqual(result["storageAccessBlockedBy"], [])
        self.assertGreater(result["bedPaxGapCm"], 39)
        self.assertAlmostEqual(
            (cabinet["positionPx"]["rotationDeg"] - bed["positionPx"]["rotationDeg"]) % 360,
            180,
        )
        bed_angle = math.radians(bed["positionPx"]["rotationDeg"])
        bed_long_axis = (-math.sin(bed_angle), math.cos(bed_angle))
        cabinet_from_bed = (
            cabinet["positionPx"]["center"][0] - bed["positionPx"]["center"][0],
            cabinet["positionPx"]["center"][1] - bed["positionPx"]["center"][1],
        )
        self.assertLess(
            cabinet_from_bed[0] * bed_long_axis[0]
            + cabinet_from_bed[1] * bed_long_axis[1],
            0,
        )
        access_zone = wardrobe_access_polygon(cabinet, self.apartment["scale"]["cmPerPixel"], 35)
        access_from_cabinet = (
            access_zone.centroid.x - cabinet["positionPx"]["center"][0],
            access_zone.centroid.y - cabinet["positionPx"]["center"][1],
        )
        self.assertGreater(
            access_from_cabinet[0] * bed_long_axis[0]
            + access_from_cabinet[1] * bed_long_axis[1],
            0,
        )

    def test_both_rotated_keeps_commode_at_one_wall_anchor_for_every_bed_width(self):
        positions = {
            tuple(next(obj for obj in layout["objects"] if obj["id"] == "owned-bedside-cabinet")["positionPx"]["center"])
            for layout in self.furniture["layouts"]
            if layout["selection"]["arrangementId"] == "bath-wall-both-rotated"
        }
        self.assertEqual(positions, {(294.8577, 163.7061)})

    def test_rotated_beds_reserve_approximately_20_cm_behind_headboard(self):
        wall = next(item for item in self.apartment["walls"] if item["id"] == "wall-outer-nw")
        wall_axis = LineString([wall["start"], wall["end"]])
        wall_half_thickness_cm = wall["thicknessPx"] * self.apartment["scale"]["cmPerPixel"] / 2
        for bed_variant_id in ("current-bed-90", "new-bed-90", "new-bed-120"):
            layout = next(
                item
                for item in self.furniture["layouts"]
                if item["selection"]["arrangementId"] == "bath-wall-both-rotated"
                and item["selection"]["bedVariantId"] == bed_variant_id
                and item["selection"]["minifridgePlacementId"] == "endcap-extension"
            )
            bed = next(obj for obj in layout["objects"] if obj["type"] == "bed")
            clear_gap_cm = (
                wall_axis.distance(furniture_polygon(bed, self.apartment["scale"]["cmPerPixel"]))
                * self.apartment["scale"]["cmPerPixel"]
                - wall_half_thickness_cm
            )
            self.assertGreater(clear_gap_cm, 15)
            self.assertLess(clear_gap_cm, 22)

    def test_every_bed_option_is_generated_in_every_orientation(self):
        expected_beds = {"current-bed-90", "new-bed-90", "new-bed-120", "new-bed-140", "new-bed-160", "new-bed-180"}
        for arrangement_id in {"divider", "bath-wall-bed-shifted", "bath-wall-both-rotated", "east-wall-wardrobe", "kitchen-wall-wardrobe"}:
            actual = {
                layout["selection"]["bedVariantId"]
                for layout in self.furniture["layouts"]
                if layout["selection"]["arrangementId"] == arrangement_id
            }
            self.assertEqual(actual, expected_beds)

    def test_every_valid_scenario_keeps_at_least_one_loggia_door_usable(self):
        for layout in self.furniture["layouts"]:
            result = self.evaluate(layout)
            if result["valid"]:
                self.assertGreaterEqual(result["usableLoggiaDoors"], 1, layout["id"])

    def test_upper_desk_remains_available_when_bedroom_loggia_door_opens_80_percent(self):
        scenario_id = "scenario-bath-wall-both-rotated-new-bed-120-pax-150-quick-150-150-pax-access-0-fridge-kitchen-back-wall"
        layout = next(item for item in self.furniture["layouts"] if item["id"] == scenario_id)
        result = self.evaluate(layout)
        self.assertTrue(result["valid"], result["reasons"])
        self.assertGreaterEqual(result["doorOpeningFractions"]["door-loggia-bedroom"], 0.8)
        self.assertNotIn("door-loggia-bedroom", result["blockedBy"])

    def test_east_balcony_wall_arrangement_accepts_150_cm_pax_with_central_desk(self):
        scenario_id = "scenario-east-wall-wardrobe-new-bed-90-pax-150-quick-150-150-living-room-centre-pax-access-0-fridge-kitchen-back-wall"
        layout = next(item for item in self.furniture["layouts"] if item["id"] == scenario_id)
        result = self.evaluate(layout)
        pax = next(item for item in layout["objects"] if item["type"] == "wardrobe")
        desk = next(item for item in layout["objects"] if item["type"] == "desk")
        self.assertTrue(result["valid"], result["reasons"])
        self.assertEqual(pax["dimensionsCm"]["width"], 149.6)
        self.assertEqual(pax["positionPx"]["rotationDeg"], -90)
        self.assertEqual(desk["positionPx"]["topLeft"], [333, 350])

    def test_east_balcony_wall_arrangement_rejects_pax_wider_than_wall_segment(self):
        scenario_id = "scenario-east-wall-wardrobe-new-bed-90-pax-200-quick-150-150-living-room-centre-pax-access-0-fridge-kitchen-back-wall"
        layout = next(item for item in self.furniture["layouts"] if item["id"] == scenario_id)
        result = self.evaluate(layout)
        self.assertFalse(result["valid"])
        self.assertIn("exceeds the 167 cm fixed balcony-wall segment", " ".join(result["reasons"]))

    def test_east_balcony_wall_arrangement_allows_rotated_desk_in_kitchen_balcony_corner(self):
        scenario_id = "scenario-east-wall-wardrobe-new-bed-90-pax-150-quick-150-150-kitchen-balcony-corner-pax-access-0-fridge-kitchen-back-wall"
        layout = next(item for item in self.furniture["layouts"] if item["id"] == scenario_id)
        result = self.evaluate(layout)
        desk = next(item for item in layout["objects"] if item["type"] == "desk")
        self.assertTrue(result["valid"], result["reasons"])
        self.assertEqual(desk["positionPx"], {"topLeft": [394, 527], "rotationDeg": -90, "handedness": "left"})

    def test_kitchen_wall_arrangement_supports_upper_and_between_doors_desks(self):
        prefix = "scenario-kitchen-wall-wardrobe-new-bed-90-pax-150-quick-150-150"
        scenario_ids = [
            f"{prefix}-pax-access-0-fridge-kitchen-back-wall",
            f"{prefix}-balcony-between-doors-pax-access-0-fridge-kitchen-back-wall",
        ]
        for scenario_id in scenario_ids:
            layout = next(item for item in self.furniture["layouts"] if item["id"] == scenario_id)
            self.assertTrue(self.evaluate(layout)["valid"], scenario_id)

    def test_lower_desk_position_preserves_the_upper_balcony_door(self):
        for layout in self.furniture["layouts"]:
            if layout["selection"]["deskPlacementId"] != "lower-balcony-corner":
                continue
            result = self.evaluate(layout)
            self.assertNotIn("door-balcony-upper", result["blockedBy"], layout["id"])
            self.assertIn("vernal-l-desk", result["blockedBy"].get("door-balcony-lower", []), layout["id"])

    def test_every_valid_scenario_keeps_every_furniture_item_out_of_pax_access_zone(self):
        for layout in self.furniture["layouts"]:
            result = self.evaluate(layout)
            if result["valid"]:
                self.assertEqual(result["wardrobeAccessBlockedBy"], [], layout["id"])

    def test_access_validation_uses_each_scenario_depth(self):
        base_id = "scenario-bath-wall-both-rotated-new-bed-120-pax-200-quick-150-150"
        layouts = {layout["selection"]["paxAccessDepthCm"]: layout for layout in self.furniture["layouts"] if layout["id"] in {base_id, f"{base_id}-pax-access-0", f"{base_id}-pax-access-30", f"{base_id}-pax-access-60"}}
        self.assertEqual(set(layouts), {0, 30, 45, 60})
        results = {depth: self.evaluate(layout) for depth, layout in layouts.items()}
        self.assertEqual({depth: result["wardrobeAccessDepthCm"] for depth, result in results.items()}, {0: 0, 30: 30, 45: 45, 60: 60})
        self.assertEqual(results[0]["wardrobeAccessBlockedBy"], [])
        self.assertIn("sleeping-bed", results[45]["wardrobeAccessBlockedBy"])
        self.assertIn("sleeping-bed", results[60]["wardrobeAccessBlockedBy"])

    def test_every_valid_scenario_keeps_cabinet_drawers_usable(self):
        for layout in self.furniture["layouts"]:
            result = self.evaluate(layout)
            if result["valid"]:
                self.assertEqual(result["storageAccessBlockedBy"], [], layout["id"])

    def test_commode_in_front_of_pax_is_always_invalid(self):
        layout = deepcopy(next(item for item in self.furniture["layouts"] if item["id"] == self.furniture["activeLayoutId"]))
        pax = next(obj for obj in layout["objects"] if obj["type"] == "wardrobe")
        cabinet = next(obj for obj in layout["objects"] if obj["type"] == "storage")
        access_center = wardrobe_access_polygon(pax, self.apartment["scale"]["cmPerPixel"]).centroid
        cabinet["positionPx"] = {"center": [access_center.x, access_center.y], "rotationDeg": pax["positionPx"]["rotationDeg"]}
        result = self.evaluate(layout)
        self.assertFalse(result["valid"])
        self.assertIn(cabinet["id"], result["wardrobeAccessBlockedBy"])

    def test_pax_access_zone_never_conflicts_with_a_door_in_valid_scenarios(self):
        door_ids = {door["id"] for door in self.apartment["doors"]}
        for layout in self.furniture["layouts"]:
            result = self.evaluate(layout)
            if result["valid"]:
                self.assertTrue(door_ids.isdisjoint(result["wardrobeAccessBlockedBy"]), layout["id"])

    def test_bed_in_front_of_pax_is_always_invalid(self):
        layout = deepcopy(
            next(
                item
                for item in self.furniture["layouts"]
                if item["id"] == "scenario-bath-wall-both-rotated-new-bed-120-pax-200-quick-150-150"
            )
        )
        result = self.evaluate(layout)
        self.assertFalse(result["valid"])
        self.assertIn("sleeping-bed", result["wardrobeAccessBlockedBy"])

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
        result = self.evaluate(layout)
        self.assertFalse(result["valid"])
        self.assertIn("At least one Loggia door must remain usable.", result["reasons"])

    def test_generated_evaluations_match_geometric_results(self):
        results = [self.evaluate(layout) for layout in self.furniture["layouts"]]
        evaluations = load_json("data/scenario-evaluations.json")
        self.assertEqual(sum(result["valid"] for result in results), evaluations["validCount"])
        self.assertGreater(evaluations["validCount"], 0)
        active = next(result for result in results if result["id"] == self.furniture["activeLayoutId"])
        self.assertTrue(active["valid"])


if __name__ == "__main__":
    unittest.main()
