#!/usr/bin/env python3
"""Generate the deterministic bed × PAX × desk furniture scenario matrix."""

from __future__ import annotations

import json
import itertools
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


def shift_position_along_width_axis(position, shift_px):
    """Slide a bed along its headboard wall without changing wall contact."""
    shifted = json.loads(json.dumps(position))
    angle = math.radians(shifted["rotationDeg"])
    shifted["center"] = [
        round(shifted["center"][0] + math.cos(angle) * shift_px, 4),
        round(shifted["center"][1] + math.sin(angle) * shift_px, 4),
    ]
    return shifted


def shift_position_away_from_headboard_wall(position, gap_cm, cm_per_pixel):
    """Create a free strip behind the headboard for a recessed door leaf."""
    shifted = json.loads(json.dumps(position))
    angle = math.radians(shifted["rotationDeg"])
    shift_px = gap_cm / cm_per_pixel
    shifted["center"] = [
        round(shifted["center"][0] - math.sin(angle) * shift_px, 4),
        round(shifted["center"][1] + math.cos(angle) * shift_px, 4),
    ]
    return shifted


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
    """Anchor the L desk to either the upper or lower right room corner."""
    position = json.loads(json.dumps(base["positionPx"]))
    if "wallContactCornerPx" not in base:
        return position
    anchor_x, anchor_y = base["wallContactCornerPx"]
    width_px = selected_variant["dimensionsCm"]["width"] / cm_per_pixel
    rotation = position.get("rotationDeg", 0) % 360
    handedness = position.get("handedness")
    if rotation == 0 and handedness == "right":
        position["topLeft"] = [round(anchor_x - width_px, 4), anchor_y]
    elif rotation == 90 and handedness == "right":
        position["topLeft"] = [anchor_x, round(anchor_y - width_px, 4)]
    else:
        raise ValueError("Unsupported wall-corner desk orientation.")
    return position


def bedside_position(bed_position_px, bed_variant, bedside_variant, bedside_base, arrangement, cm_per_pixel):
    """Place the cabinet beside a bed side/end without obstructing the PAX front."""
    angle = math.radians(bed_position_px["rotationDeg"])
    cross_axis = (math.cos(angle), math.sin(angle))
    long_axis = (-math.sin(angle), math.cos(angle))
    placement = arrangement.get("bedsidePlacement", "side")
    direction = arrangement.get("bedsideDirection", 1)
    gap_cm = bedside_base.get("gapToBedCm", 0)
    if placement == "side":
        cross_offset_px = direction * (
            bed_variant["dimensionsCm"]["width"] / 2
            + bedside_variant["dimensionsCm"]["depth"] / 2
            + gap_cm
        ) / cm_per_pixel
        long_offset_px = 0
        rotation_deg = bed_position_px["rotationDeg"] + 90
    elif placement == "end":
        cross_offset_px = 0
        long_offset_px = direction * (
            bed_variant["dimensionsCm"]["depth"] / 2
            + bedside_variant["dimensionsCm"]["depth"] / 2
            + gap_cm
        ) / cm_per_pixel
        rotation_deg = bed_position_px["rotationDeg"]
    else:
        raise ValueError(f"Unsupported bedside placement: {placement}")
    bed_center = bed_position_px["center"]
    rotation_offset = arrangement.get("bedsideRotationOffsetDeg", 0)
    return {
        "center": [
            round(bed_center[0] + cross_axis[0] * cross_offset_px + long_axis[0] * long_offset_px, 4),
            round(bed_center[1] + cross_axis[1] * cross_offset_px + long_axis[1] * long_offset_px, 4),
        ],
        "rotationDeg": round(rotation_deg + rotation_offset, 4),
    }


def main():
    catalog = load_json("data/furniture-catalog.json")
    matrix = load_json("data/scenario-matrix.json")
    apartment = load_json("data/apartment.json")
    variants = variant_map(catalog)
    variant_families = family_by_variant(catalog)
    placements = matrix["placements"]
    base_bed_variant = variants[placements["bed"]["baseVariantId"]]
    base_pax_variant = variants[placements["pax"]["baseVariantId"]]
    bedside_variant = variants[placements["bedside"]["variantId"]]
    desk_placements = matrix.get("deskPlacements") or [{"id": "upper-loggia-corner", **placements["desk"]}]
    scenarios = []

    arrangements = matrix.get("arrangements") or [{"id": "divider", "label": "Standard"}]
    for arrangement in arrangements:
        bed_ids = arrangement.get("bedVariantIds", matrix["axes"]["bedVariantIds"])
        for bed_id in bed_ids:
            for pax_id in matrix["axes"]["paxVariantIds"]:
                for desk_id, desk_placement, pax_access_depth_cm in itertools.product(
                    matrix["axes"]["deskVariantIds"],
                    desk_placements,
                    matrix["axes"].get("paxAccessDepthCm", [45]),
                ):
                    bed = variants[bed_id]
                    pax = variants[pax_id]
                    desk = variants[desk_id]
                    if arrangement["id"] == "divider":
                        scenario_id = f"scenario-{bed_id}-{pax_id}-{desk_id}"
                    else:
                        scenario_id = f"scenario-{arrangement['id']}-{bed_id}-{pax_id}-{desk_id}"
                    if desk_placement["id"] != "upper-loggia-corner":
                        scenario_id = f"{scenario_id}-{desk_placement['id']}"
                    # Keep all existing 45 cm URLs stable. Other access depths use
                    # an explicit suffix so the axis can be shared/bookmarked.
                    if pax_access_depth_cm != 45:
                        scenario_id = f"{scenario_id}-pax-access-{pax_access_depth_cm}"
                    if arrangement.get("bedPositionPx"):
                        arrangement_bed_base = variants[arrangement.get("bedBaseVariantId", "current-bed-90")]
                        arrangement_bed_placement = {
                            **placements["bed"],
                            "positionPx": arrangement["bedPositionPx"],
                            "keepWallSideFixed": True,
                        }
                        bed_position_px = bed_position(
                            arrangement_bed_placement,
                            arrangement_bed_base,
                            bed,
                            apartment["scale"]["cmPerPixel"],
                        )
                    else:
                        bed_position_px = bed_position(
                            placements["bed"], base_bed_variant, bed, apartment["scale"]["cmPerPixel"]
                        )
                    wall_shift_px = arrangement.get("bedWallShiftPxByVariant", {}).get(bed_id, 0)
                    if wall_shift_px:
                        bed_position_px = shift_position_along_width_axis(bed_position_px, wall_shift_px)
                    headboard_gap_cm = arrangement.get("bedHeadboardWallGapCm", 0)
                    if headboard_gap_cm:
                        bed_position_px = shift_position_away_from_headboard_wall(
                            bed_position_px, headboard_gap_cm, apartment["scale"]["cmPerPixel"]
                        )
                    pax_position_px = arrangement.get("paxPositionPx") or pax_position(
                        placements["pax"], base_pax_variant, pax, apartment["scale"]["cmPerPixel"]
                    )
                    bedside_position_px = arrangement.get("bedsidePositionPx") or bedside_position(
                        bed_position_px,
                        bed,
                        bedside_variant,
                        placements["bedside"],
                        arrangement,
                        apartment["scale"]["cmPerPixel"],
                    )
                    scenarios.append(
                        {
                            "id": scenario_id,
                            "name": f"{arrangement['label']} · {bed['label']} · {pax['label']} · {pax_access_depth_cm} cm PAX-Zugriff · {desk['label']} · {desk_placement['label']}",
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
                                "paxAccessDepthCm": pax_access_depth_cm,
                                "deskVariantId": desk_id,
                                "deskPlacementId": desk_placement["id"],
                            },
                            "notes": [
                                (
                                    f"Das Kopfende hält {headboard_gap_cm:g} cm Abstand zur Wand, damit die zurückgesetzte Loggiatür in der Laibung öffnen kann."
                                    if headboard_gap_cm
                                    else "Die wandseitige Außenkante des Betts bleibt innerhalb der jeweiligen Anordnung am Wandanker."
                                ),
                                f"Vor dem PAX sind {pax_access_depth_cm} cm als frei zu haltende Zugriffsfläche reserviert; 0 cm bedeutet keine zusätzliche Reserve über die Stellfläche hinaus.",
                                (
                                    "Die vorhandene Kommode steht in der geprüften Schlafbereichsecke; vor den Schubladen bleiben 35 cm Bedienfläche frei."
                                    if arrangement.get("bedsidePositionPx")
                                    else "Die vorhandene Kommode steht mit 2 cm Planungsabstand am Bettende oder an der Bettseite; vor den Schubladen bleiben 35 cm Bedienfläche frei."
                                ),
                                desk_placement["note"],
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
                                    "id": placements["bedside"]["id"],
                                    "templateId": placements["bedside"]["templateId"],
                                    "variantId": placements["bedside"]["variantId"],
                                    "positionPx": bedside_position_px,
                                },
                                {
                                    "id": placements["desk"]["id"],
                                    "templateId": placements["desk"]["templateId"],
                                    "variantId": desk_id,
                                    "positionPx": desk_position(
                                        desk_placement, desk, apartment["scale"]["cmPerPixel"]
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
