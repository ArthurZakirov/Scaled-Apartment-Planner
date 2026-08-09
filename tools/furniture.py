"""Resolve product templates and variants into renderable scenario objects."""

from __future__ import annotations

import copy
from typing import Any


def catalog_index(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {family["id"]: family for family in catalog["families"]}


def variant_index(family: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {variant["id"]: variant for variant in family["variants"]}


def resolve_scenario_object(
    placement: dict[str, Any], catalog: dict[str, Any]
) -> dict[str, Any]:
    families = catalog_index(catalog)
    family = families[placement["templateId"]]
    variant = variant_index(family)[placement["variantId"]]
    resolved = {
        "id": placement["id"],
        "templateId": family["id"],
        "variantId": variant["id"],
        "type": family["type"],
        "name": variant["label"],
        "sourceUrl": variant.get("sourceUrl", family.get("sourceUrl")),
        "confidence": variant.get("confidence", family["confidence"]),
        "dimensionsCm": copy.deepcopy(variant["dimensionsCm"]),
        "positionPx": copy.deepcopy(placement["positionPx"]),
        "render": copy.deepcopy(variant["render"]),
    }
    for key in ("mattressCm", "modules", "heightRangeCm"):
        if key in variant:
            resolved[key] = copy.deepcopy(variant[key])
    for key in ("requiresAnchoring", "safetyNote", "doorType", "planningDepthCm", "estimateNote", "headEdge", "accessEdge", "accessLabel", "accessDepthCm"):
        if key in family:
            resolved[key] = copy.deepcopy(family[key])
    if "intentionalDoorBlocks" in placement:
        resolved["intentionalDoorBlocks"] = list(placement["intentionalDoorBlocks"])
    return resolved


def resolve_scenario(
    scenario: dict[str, Any], catalog: dict[str, Any]
) -> dict[str, Any]:
    resolved = copy.deepcopy(scenario)
    resolved["objects"] = [
        resolve_scenario_object(placement, catalog)
        for placement in scenario["objects"]
    ]
    return resolved


def resolve_scenario_data(
    scenario_data: dict[str, Any], catalog: dict[str, Any]
) -> dict[str, Any]:
    return {
        "activeLayoutId": scenario_data["activeScenarioId"],
        "layouts": [
            resolve_scenario(scenario, catalog)
            for scenario in scenario_data["scenarios"]
        ],
    }
