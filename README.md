# Scaled Apartment Planner

A structured, agent-controlled apartment planner for Wohnung 264. The project reconstructs the non-rectangular floor plan as SVG geometry and keeps the original source image only as an immutable calibration reference.

## Current state

The planner currently includes:

- reconstructed sloped exterior envelope, interior partitions, doors, loggia, and balcony;
- a separate fixed-kitchen layer;
- a separate furniture layer;
- three real MALM frame sizes, three modular PAX widths, and four VERNAL L-desk variants;
- a generated 3 × 3 × 4 matrix with 36 explicit scenarios;
- automatic filtering and ranking of geometrically valid scenarios;
- previous/next navigation through valid proposals with score, minimum furniture gap, free floor estimate, and usable exterior doors;
- automatic door-swing intersection checks;
- a normal vector-only view;
- a calibration route that overlays the vector geometry on the immutable source image;
- parametric wall profiles whose parallel and perpendicular edges are derived from one baseline;
- Python/Shapely validation for angles, connections, and wall-to-fixture clearances;
- negative regression tests that prove invalid geometry is rejected.

## Run locally

```bash
npm run dev
```

Open:

- `http://127.0.0.1:4173/` for the clean planner;
- `http://127.0.0.1:4173/calibration/` for the original-image overlay.

## Validate

```bash
python3 -m pip install -r requirements.txt
npm run validate
```

The current expected result is:

- `door-loggia-living` blocked by the desk;
- `door-balcony-upper` blocked by the desk;
- entrance, bathroom, bedroom-side loggia door, and lower balcony door clear.
- 12 of the 36 generated furniture scenarios geometrically valid.

After editing the catalog or scenario matrix, regenerate derived data before validating:

```bash
npm run generate:scenarios
```

## Important accuracy warning

The marketing floor plan explicitly says it is not to scale. The broker confirmed that the apartment entrance door is 1 metre wide. The current 1.52 cm/px scale is anchored to that door. All other dimensions remain estimates because the marketing floor plan explicitly says it is not to scale.

Do not use the current measurements for final purchase decisions where small clearances matter.

## Data model

- `data/apartment.json`: building geometry, spaces, walls, doors, windows, single-door-anchored estimated scale;
- `data/geometry-rules.json`: declarative parallelism, orthogonality, connection, and clearance constraints;
- `data/fixed-fixtures.json`: fitted kitchen and other permanent elements;
- `data/furniture-catalog.json`: reusable MALM, PAX, and VERNAL templates with verified exterior dimensions;
- `data/scenario-matrix.json`: scenario axes and base placements;
- `data/layout-scenarios.json`: generated 36-layout matrix;
- `data/scenario-evaluations.json`: generated validation metrics and ranked valid scenario IDs;
- `data/furniture.json`: lightweight manifest linking the furniture data layers;
- `data/layout-constraints.json`: door and clearance policies;
- `the immutable source URL in `data/apartment.json``: immutable reference;
- `AGENTS.md`: binding rules for Codex and other coding agents.

## Agent interaction model

The user-facing app intentionally contains no furniture form. A coding agent changes `data/furniture.json`, runs validation, and visually checks the result. Later this can be wrapped in CLI or MCP functions such as:

```text
extract_product(url)
add_furniture(product, constraints)
move_furniture(id, constraints)
rotate_furniture(id, degrees)
remove_furniture(id)
check_collisions()
check_clearances()
find_valid_placement()
render_layout()
```
