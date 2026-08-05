#!/usr/bin/env python3
"""Generate the deterministic 3 × 3 × 4 furniture scenario matrix."""

from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_json(relative: str):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def variant_map(catalog):
    return {
        variant["id"]: variant
        for family in catalog["families"]
        for variant in family["variants"]
    }


def bed_position(base, base_variant, selected_variant, cm_per_pixel):
    position = json.loads(json.dumps(base["positionPx"]))
    if not base.get("keepWallSideFixed"):
        return position
    delta_cm = selected_variant["dimensionsCm"]["width"] - base_variant["dimensionsCm"]["width"]
    shift_px = delta_cm / cm_per_pixel / 2
    angle = math.radians(position["rotationDeg"])
    position["center"] = [
        round(position["center"][0] + math.cos(angle) * shift_px, 4),
        round(position["center"][1] + math.sin(angle) * shift_px, 4),
    ]
    return position


def main():
    catalog = load_json("data/furniture-catalog.json")
    matrix = load_json("data/scenario-matrix.json")
    apartment = load_json("data/apartment.json")
    variants = variant_map(catalog)
    placements = matrix["placements"]
    base_bed_variant = variants[placements["bed"]["baseVariantId"]]
    scenarios = []

    for bed_id in matrix["axes"]["bedVariantIds"]:
        for pax_id in matrix["axes"]["paxVariantIds"]:
            for desk_id in matrix["axes"]["deskVariantIds"]:
                bed = variants[bed_id]
                pax = variants[pax_id]
                desk = variants[desk_id]
                scenario_id = f"scenario-{bed_id}-{pax_id}-{desk_id}"
                scenarios.append(
                    {
                        "id": scenario_id,
                        "name": f"{bed['label']} · {pax['label']} · {desk['label']}",
                        "status": "generated_experiment",
                        "selection": {
                            "bedVariantId": bed_id,
                            "paxVariantId": pax_id,
                            "deskVariantId": desk_id,
                        },
                        "notes": [
                            "Bed remains aligned to the sloped northwest wall using its external frame footprint.",
                            "PAX keeps the same comparison center; its real modular corpus width changes by variant.",
                            "Desk keeps the same upper-right corner anchor and handedness.",
                            "PAX requires a real anchoring solution before purchase or installation.",
                        ],
                        "objects": [
                            {
                                "id": placements["pax"]["id"],
                                "templateId": placements["pax"]["templateId"],
                                "variantId": pax_id,
                                "positionPx": placements["pax"]["positionPx"],
                            },
                            {
                                "id": placements["bed"]["id"],
                                "templateId": placements["bed"]["templateId"],
                                "variantId": bed_id,
                                "positionPx": bed_position(
                                    placements["bed"], base_bed_variant, bed, apartment["scale"]["cmPerPixel"]
                                ),
                            },
                            {
                                "id": placements["desk"]["id"],
                                "templateId": placements["desk"]["templateId"],
                                "variantId": desk_id,
                                "positionPx": placements["desk"]["positionPx"],
                            },
                        ],
                    }
                )

    output = {
        "version": 1,
        "activeScenarioId": matrix["activeScenarioId"],
        "generatedFrom": "data/scenario-matrix.json",
        "scenarioCount": len(scenarios),
        "scenarios": scenarios,
    }
    target = ROOT / "data/layout-scenarios.json"
    target.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Generated {len(scenarios)} scenarios in {target}")


if __name__ == "__main__":
    main()
