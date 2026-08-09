# Scaled Apartment Planner

A structured, agent-controlled apartment planner for Wohnung 264. The project reconstructs the non-rectangular floor plan as SVG geometry and keeps the original source image only as an immutable calibration reference.

## Current state

The planner currently includes:

- reconstructed sloped exterior envelope, interior partitions, doors, loggia, and balcony;
- a separate fixed-kitchen layer;
- a separate furniture layer;
- the current 111 × 204 cm bed, the existing 57.5 × 43 × 54 cm bedside cabinet, five estimated new-bed footprints for 90–180 cm mattresses, three modular PAX widths, and four VERNAL L-desk contexts;
- three orientation concepts: transverse divider, PAX along the bathroom wall with shifted bed, and PAX plus bed rotated by 90°;
- 1,728 explicit generated scenarios with geometric and installation-safety classification, including two independent VERNAL positions and four independently selectable PAX access reserves;
- dedicated selectors for current/new bed, mattress width, PAX width, PAX access reserve (0/30/45/60 cm), and VERNAL position while the selected desk size remains fixed;
- dimension selectors preserve the active orientation and other furniture choices instead of silently switching to another layout concept;
- the rotated bed/PAX geometry can clear the Loggia door with mattresses up to 120 cm, but remains diagnostic-only because the bed blocks the required open-PAX access strip;
- the recessed bedroom-Loggia door reveal is visible in the plan and reserves a 20 cm opening strip behind the rotated bed headboard;
- the approximately 26 px Loggia-separation wall rendering accompanies a separately calibrated usable interior boundary; the former “PAX an Badwand” comparison remains in diagnostics but is no longer selectable because it does not fit the corrected interior;
- strict filtering to geometrically valid bedroom combinations with score, bed-to-PAX gap, free floor estimate, and usable loggia access;
- a user-selected 0/30/45/60 cm PAX opening zone that no bed, cabinet, desk, or other furniture may obstruct; 45 cm remains the default and 0 cm reserves no area beyond the footprint;
- integrated orientation markers for bed head/pillows, open PAX access, and cabinet drawer direction;
- a visible selected access zone in front of the PAX (hidden at 0 cm) and 35 cm in front of the cabinet drawers, plus a distinct warning state when a layout fits geometrically but still lacks a safe anchoring solution;
- a direct three-button switch between the transverse divider and both bathroom-wall concepts;
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
- the valid count derived automatically from all 1,728 generated furniture scenarios.

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
- `data/furniture-catalog.json`: current furniture, estimated new-bed footprints, and reusable PAX/VERNAL templates;
- `data/scenario-matrix.json`: scenario axes and base placements;
- `data/layout-scenarios.json`: generated 1,728-layout matrix;
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
