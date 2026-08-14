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


def minifridge_position(placement, selected_variant, apartment):
    """Anchor the fridge to geometry derived from the Garderobe wall profile."""
    profile = next(
        item for item in apartment.get("wallProfiles", [])
        if item["id"] == placement["profileId"]
    )
    start = profile["baselineStart"]
    end = profile["baselineEnd"]
    axis_x, axis_y = end[0] - start[0], end[1] - start[1]
    axis_length = math.hypot(axis_x, axis_y)
    if not axis_length:
        raise ValueError("Minifridge profile anchor requires a non-zero baseline.")
    axis_x, axis_y = axis_x / axis_length, axis_y / axis_length
    side_direction = -1 if profile.get("offsetSide") == "left" else 1
    side_x = side_direction * -axis_y
    side_y = side_direction * axis_x
    far_end = [
        end[0] + side_x * profile["depthPx"],
        end[1] + side_y * profile["depthPx"],
    ]
    cm_per_pixel = apartment["scale"]["cmPerPixel"]
    width_px = selected_variant["dimensionsCm"]["width"] / cm_per_pixel
    depth_px = selected_variant["dimensionsCm"]["depth"] / cm_per_pixel
    wall_half_px = profile["wallThicknessPx"] / 2

    if placement["anchor"] == "end_cap_extension":
        cap_midpoint = [(end[0] + far_end[0]) / 2, (end[1] + far_end[1]) / 2]
        center = [
            cap_midpoint[0] + axis_x * (wall_half_px + depth_px / 2),
            cap_midpoint[1] + axis_y * (wall_half_px + depth_px / 2),
        ]
        rotation_deg = math.degrees(math.atan2(side_y, side_x))
    elif placement["anchor"] == "kitchen_side_back_wall":
        distance_from_start_px = placement["distanceFromProfileStartCm"] / cm_per_pixel
        far_start = [
            start[0] + side_x * profile["depthPx"],
            start[1] + side_y * profile["depthPx"],
        ]
        center = [
            far_start[0] + axis_x * distance_from_start_px + side_x * (wall_half_px + depth_px / 2),
            far_start[1] + axis_y * distance_from_start_px + side_y * (wall_half_px + depth_px / 2),
        ]
        # The first polygon edge is the marked door edge. Using the negative
        # profile axis as width direction makes that edge face the kitchen.
        rotation_deg = math.degrees(math.atan2(-axis_y, -axis_x))
    else:
        raise ValueError(f"Unsupported minifridge anchor: {placement['anchor']}")

    return {
        "center": [round(center[0], 4), round(center[1], 4)],
        "rotationDeg": round(rotation_deg, 4),
    }


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
    elif placement == "head-side":
        cross_offset_px = direction * (
            bed_variant["dimensionsCm"]["width"] / 2
            + bedside_variant["dimensionsCm"]["width"] / 2
            + gap_cm
        ) / cm_per_pixel
        long_offset_px = arrangement.get("bedsideEndDirection", -1) * (
            bed_variant["dimensionsCm"]["depth"] / 2
            - bedside_variant["dimensionsCm"]["depth"] / 2
        ) / cm_per_pixel
        # The drawer front faces the foot end, so drawers travel parallel to
        # the bed instead of opening into the wall or across the bedside gap.
        rotation_deg = bed_position_px["rotationDeg"] + 180
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


def bed_position_from_bedside(
    bed_position_px, bed_variant, bedside_position_px, bedside_variant, bedside_base, arrangement, cm_per_pixel
):
    """Anchor a bed beside a wall-fixed cabinet instead of moving the cabinet with the bed."""
    if arrangement.get("bedsidePlacement") != "head-side":
        raise ValueError("Wall-fixed bedside anchoring currently requires head-side placement.")
    angle = math.radians(bed_position_px["rotationDeg"])
    cross_axis = (math.cos(angle), math.sin(angle))
    long_axis = (-math.sin(angle), math.cos(angle))
    direction = arrangement.get("bedsideDirection", 1)
    gap_cm = bedside_base.get("gapToBedCm", 0)
    cross_offset_px = direction * (
        bed_variant["dimensionsCm"]["width"] / 2
        + bedside_variant["dimensionsCm"]["width"] / 2
        + gap_cm
    ) / cm_per_pixel
    long_offset_px = arrangement.get("bedsideEndDirection", -1) * (
        bed_variant["dimensionsCm"]["depth"] / 2
        - bedside_variant["dimensionsCm"]["depth"] / 2
    ) / cm_per_pixel
    return {
        "center": [
            round(
                bedside_position_px["center"][0]
                - cross_axis[0] * cross_offset_px
                - long_axis[0] * long_offset_px,
                4,
            ),
            round(
                bedside_position_px["center"][1]
                - cross_axis[1] * cross_offset_px
                - long_axis[1] * long_offset_px,
                4,
            ),
        ],
        "rotationDeg": bed_position_px["rotationDeg"],
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
    minifridge_variant = variants[placements["minifridge"]["variantId"]]
    desk_placements = matrix.get("deskPlacements") or [{"id": "upper-loggia-corner", **placements["desk"]}]
    minifridge_placement_map = {item["id"]: item for item in matrix["minifridgePlacements"]}
    minifridge_placements = [
        minifridge_placement_map[item_id]
        for item_id in matrix["axes"]["minifridgePlacementIds"]
    ]
    scenarios = []

    arrangements = matrix.get("arrangements") or [{"id": "divider", "label": "Standard"}]
    for arrangement in arrangements:
        bed_ids = arrangement.get("bedVariantIds", matrix["axes"]["bedVariantIds"])
        for bed_id in bed_ids:
            for pax_id in matrix["axes"]["paxVariantIds"]:
                for desk_id, desk_placement, pax_access_depth_cm, minifridge_placement in itertools.product(
                    matrix["axes"]["deskVariantIds"],
                    desk_placements,
                    matrix["axes"].get("paxAccessDepthCm", [45]),
                    minifridge_placements,
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
                    # Placement A remains suffix-free so existing scenario URLs
                    # keep selecting the default fridge placement.
                    if minifridge_placement["id"] != "endcap-extension":
                        scenario_id = f"{scenario_id}-fridge-{minifridge_placement['id']}"
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
                    headboard_gap_cm = arrangement.get("bedHeadboardWallGapCm", 0)
                    if arrangement.get("bedPositionFromBedside"):
                        bed_position_px = bed_position_from_bedside(
                            bed_position_px,
                            bed,
                            arrangement["bedsidePositionPx"],
                            bedside_variant,
                            placements["bedside"],
                            arrangement,
                            apartment["scale"]["cmPerPixel"],
                        )
                    else:
                        wall_shift_px = arrangement.get("bedWallShiftPxByVariant", {}).get(bed_id, 0)
                        if wall_shift_px:
                            bed_position_px = shift_position_along_width_axis(bed_position_px, wall_shift_px)
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
                            "name": f"{arrangement['label']} · {bed['label']} · {pax['label']} · {pax_access_depth_cm} cm PAX-Zugriff · {desk['label']} · {desk_placement['label']} · Kühlschrank {minifridge_placement['label']}",
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
                                "minifridgePlacementId": minifridge_placement["id"],
                            },
                            "notes": [
                                (
                                    f"Das Kopfende hält {headboard_gap_cm:g} cm Abstand zur Wand, damit die zurückgesetzte Loggiatür in der Laibung öffnen kann."
                                    if headboard_gap_cm
                                    else "Die wandseitige Außenkante des Betts bleibt innerhalb der jeweiligen Anordnung am Wandanker."
                                ),
                                f"Vor dem PAX sind {pax_access_depth_cm} cm als frei zu haltende Zugriffsfläche reserviert; 0 cm bedeutet keine zusätzliche Reserve über die Stellfläche hinaus.",
                                (
                                    "Die vorhandene Kommode bleibt am festen Loggia-Wandanker; jede Bettbreite wird mit 2 cm Abstand daneben gesetzt und vor den Schubladen bleiben 35 cm Bedienfläche frei."
                                    if arrangement.get("bedPositionFromBedside")
                                    else "Die vorhandene Kommode steht in der geprüften Schlafbereichsecke; vor den Schubladen bleiben 35 cm Bedienfläche frei."
                                    if arrangement.get("bedsidePositionPx")
                                    else (
                                        "Die vorhandene Kommode steht mit 2 cm Planungsabstand seitlich am Kopfende; vor den Schubladen bleiben 35 cm Bedienfläche frei."
                                        if arrangement.get("bedsidePlacement") == "head-side"
                                        else "Die vorhandene Kommode steht mit 2 cm Planungsabstand am Bettende oder an der Bettseite; vor den Schubladen bleiben 35 cm Bedienfläche frei."
                                    )
                                ),
                                desk_placement["note"],
                                minifridge_placement["note"],
                                "Vor der markierten Kühlschranktür bleiben 40 cm Bedienzone innerhalb der Wohnung frei.",
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
                                {
                                    "id": placements["minifridge"]["id"],
                                    "templateId": placements["minifridge"]["templateId"],
                                    "variantId": placements["minifridge"]["variantId"],
                                    "positionPx": minifridge_position(
                                        minifridge_placement, minifridge_variant, apartment
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
