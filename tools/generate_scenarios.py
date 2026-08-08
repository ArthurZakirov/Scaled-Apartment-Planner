#!/usr/bin/env python3
"""Generate the deterministic bed × PAX × desk furniture scenario matrix."""

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


def family_by_variant(catalog):
    return {
        variant["id"]: family
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


def pax_position(base, base_variant, selected_variant, cm_per_pixel):
    """Keep the bathroom-facing short end and the cross-axis position fixed."""
    position = json.loads(json.dumps(base["positionPx"]))
    if not base.get("keepBathEndFixed"):
        return position
    delta_cm = selected_variant["dimensionsCm"]["width"] - base_variant["dimensionsCm"]["width"]
    shift_px = delta_cm / cm_per_pixel / 2
    angle = math.radians(position["rotationDeg"])
    position["center"] = [
        round(position["center"][0] + math.cos(angle) * shift_px, 4),
        round(position["center"][1] + math.sin(angle) * shift_px, 4),
    ]
    return position


def desk_position(base, selected_variant, cm_per_pixel):
    """Anchor the desk's top and right edges to the two wall-contact axes."""
    position = json.loads(json.dumps(base["positionPx"]))
    if "wallContactCornerPx" not in base:
        return position
    if position.get("rotationDeg", 0) != 0 or position.get("handedness") != "right":
        raise ValueError("Wall-corner desk anchoring currently requires a right-handed, unrotated L desk.")
    anchor_x, anchor_y = base["wallContactCornerPx"]
    width_px = selected_variant["dimensionsCm"]["width"] / cm_per_pixel
    position["topLeft"] = [round(anchor_x - width_px, 4), anchor_y]
    return position


def main():
    catalog = load_json("data/furniture-catalog.json")
    matrix = load_json("data/scenario-matrix.json")
    apartment = load_json("data/apartment.json")
    variants = variant_map(catalog)
    variant_families = family_by_variant(catalog)
    placements = matrix["placements"]
    base_bed_variant = variants[placements["bed"]["baseVariantId"]]
    base_pax_variant = variants[placements["pax"]["baseVariantId"]]
    scenarios = []

    arrangements = matrix.get("arrangements") or [{"id": "divider", "label": "Standard"}]
    for arrangement in arrangements:
        bed_ids = arrangement.get("bedVariantIds", matrix["axes"]["bedVariantIds"])
        for bed_id in bed_ids:
            for pax_id in matrix["axes"]["paxVariantIds"]:
                for desk_id in matrix["axes"]["deskVariantIds"]:
                    bed = variants[bed_id]
                    pax = variants[pax_id]
                    desk = variants[desk_id]
                    if arrangement["id"] == "divider":
                        scenario_id = f"scenario-{bed_id}-{pax_id}-{desk_id}"
                    else:
                        scenario_id = f"scenario-{arrangement['id']}-{bed_id}-{pax_id}-{desk_id}"
                    bed_position_px = arrangement.get("bedPositionPx") or bed_position(
                        placements["bed"], base_bed_variant, bed, apartment["scale"]["cmPerPixel"]
                    )
                    pax_position_px = arrangement.get("paxPositionPx") or pax_position(
                        placements["pax"], base_pax_variant, pax, apartment["scale"]["cmPerPixel"]
                    )
                    scenarios.append(
                        {
                            "id": scenario_id,
                            "name": f"{arrangement['label']} · {bed['label']} · {pax['label']} · {desk['label']}",
                            "status": "generated_experiment",
                            "arrangementId": arrangement["id"],
                            "arrangementLabel": arrangement["label"],
                            "installationStatus": arrangement.get("installationStatus", "requires_engineered_solution"),
                            "kitchenExposure": arrangement.get("kitchenExposure", "unknown"),
                            "recommendation": arrangement.get("recommendation", "Befestigung vor Kauf fachlich prüfen."),
                            "selection": {
                                "arrangementId": arrangement["id"],
                                "bedVariantId": bed_id,
                                "paxVariantId": pax_id,
                                "deskVariantId": desk_id,
                            },
                            "notes": [
                                "Die wandseitige Außenkante des Betts bleibt innerhalb der jeweiligen Anordnung am Wandanker.",
                                "PAX ist offen ohne Türen geplant; seine 58 cm Tiefe bleibt unverändert.",
                                "Die obere und rechte Tischkante bleiben unabhängig von der Tischgröße an ihren Wänden.",
                                arrangement.get("recommendation", "PAX benötigt eine geprüfte Verankerungslösung."),
                            ],
                            "objects": [
                                {
                                    "id": placements["pax"]["id"],
                                    "templateId": placements["pax"]["templateId"],
                                    "variantId": pax_id,
                                    "positionPx": pax_position_px,
                                },
                                {
                                    "id": placements["bed"]["id"],
                                    "templateId": variant_families[bed_id]["id"],
                                    "variantId": bed_id,
                                    "positionPx": bed_position_px,
                                },
                                {
                                    "id": placements["desk"]["id"],
                                    "templateId": placements["desk"]["templateId"],
                                    "variantId": desk_id,
                                    "positionPx": desk_position(
                                        placements["desk"], desk, apartment["scale"]["cmPerPixel"]
                                    ),
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
