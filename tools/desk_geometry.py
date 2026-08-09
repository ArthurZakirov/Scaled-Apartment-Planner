"""Reusable geometry for L-desk work zones and fixed kitchen fixtures."""

from __future__ import annotations

from typing import Any, Iterable

from shapely.affinity import rotate, translate
from shapely.geometry import Polygon, box
from shapely.ops import unary_union


def fixed_fixture_polygon(fixture: dict[str, Any]) -> Polygon:
    """Resolve the rectangular footprint used by the fixed-fixture data layer."""
    if fixture.get("shape") != "rectangle":
        raise ValueError(f"Unsupported fixed fixture shape: {fixture.get('shape')}")
    return box(
        fixture["x"],
        fixture["y"],
        fixture["x"] + fixture["widthPx"],
        fixture["y"] + fixture["depthPx"],
    )


def fixed_fixture_union(fixtures: Iterable[dict[str, Any]]) -> Polygon:
    """Return the combined permanent-fixture footprint without double-counting overlaps."""
    return unary_union([fixed_fixture_polygon(fixture) for fixture in fixtures])


def desk_work_zone_polygon(
    desk: dict[str, Any],
    cm_per_pixel: float,
    width_cm: float = 60,
    depth_cm: float = 60,
) -> Polygon:
    """Place a rectangular chair/work zone directly inside an L-desk's cutout."""
    if desk["render"]["shape"] != "l_desk":
        raise ValueError("A chair/work zone can only be derived for an L desk.")

    dimensions = desk["dimensionsCm"]
    width = dimensions["width"] / cm_per_pixel
    main_depth = dimensions["mainTopDepth"] / cm_per_pixel
    return_depth = dimensions["returnDepth"] / cm_per_pixel
    zone_width = width_cm / cm_per_pixel
    zone_depth = depth_cm / cm_per_pixel
    cutout_width = width - return_depth
    cutout_depth = dimensions["depth"] / cm_per_pixel - main_depth
    if zone_width > cutout_width or zone_depth > cutout_depth:
        return Polygon()

    if desk["positionPx"].get("handedness") == "left":
        points = [
            (return_depth, main_depth),
            (return_depth + zone_width, main_depth),
            (return_depth + zone_width, main_depth + zone_depth),
            (return_depth, main_depth + zone_depth),
        ]
    else:
        inner_x = width - return_depth
        points = [
            (inner_x - zone_width, main_depth),
            (inner_x, main_depth),
            (inner_x, main_depth + zone_depth),
            (inner_x - zone_width, main_depth + zone_depth),
        ]

    polygon = Polygon(points)
    position = desk["positionPx"]
    polygon = rotate(polygon, position.get("rotationDeg", 0), origin=(0, 0), use_radians=False)
    x, y = position["topLeft"]
    return translate(polygon, xoff=x, yoff=y)
