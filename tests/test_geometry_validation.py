from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from geometry import expand_apartment_geometry, validate_geometry_rules  # noqa: E402


def load_json(relative: str):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


class GeometryValidationTests(unittest.TestCase):
    def setUp(self):
        source = load_json("data/apartment.json")
        self.apartment = expand_apartment_geometry(source)
        self.fixtures = load_json("data/fixed-fixtures.json")
        self.rules = load_json("data/geometry-rules.json")

    def errors_for(self, apartment=None, fixtures=None):
        errors, _ = validate_geometry_rules(
            apartment or self.apartment,
            fixtures or self.fixtures,
            self.rules,
        )
        return errors

    def test_current_geometry_satisfies_all_declared_rules(self):
        self.assertEqual(self.errors_for(), [])

    def test_skewed_wall_fails_perpendicular_rule(self):
        apartment = copy.deepcopy(self.apartment)
        wall = next(item for item in apartment["walls"] if item["id"] == "wall-bath-upper")
        wall["end"][0] += 18
        errors = self.errors_for(apartment=apartment)
        self.assertTrue(any("bath-upper-near-right-angle" in error for error in errors))

    def test_disconnected_entry_jamb_fails_connection_rule(self):
        apartment = copy.deepcopy(self.apartment)
        jamb = next(item for item in apartment["walls"] if item["id"] == "wall-entry-jamb-right")
        jamb["end"][0] += 3
        errors = self.errors_for(apartment=apartment)
        self.assertTrue(any("entry-jamb-right-connected" in error for error in errors))

    def test_kitchen_overlap_fails_clearance_rule(self):
        fixtures = copy.deepcopy(self.fixtures)
        kitchen_return = next(item for item in fixtures["fixtures"] if item["id"] == "kitchen-return")
        kitchen_return["x"] = 270
        kitchen_return["y"] = 430
        errors = self.errors_for(fixtures=fixtures)
        self.assertTrue(any("garderobe-clear-of-kitchen-return" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
