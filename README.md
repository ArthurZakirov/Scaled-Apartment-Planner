# Scaled Apartment Planner

A structured, agent-controlled apartment planner for Wohnung 264. The project reconstructs the non-rectangular floor plan as SVG geometry and keeps the original source image only as an immutable calibration reference.

## Current state

The first committed experiment includes:

- reconstructed sloped exterior envelope, interior partitions, doors, loggia, and balcony;
- a separate fixed-kitchen layer;
- a separate furniture layer;
- IKEA PAX 200 × 58 × 236 cm as a room divider;
- IKEA MALM 140 × 200 cm bed using its actual 156 × 209 cm frame footprint;
- Vernal 180 × 150 cm L-shaped desk in the corner that intentionally blocks one loggia and one balcony door;
- automatic door-swing intersection checks;
- a normal vector-only view;
- a calibration route that overlays the vector geometry on the immutable source image;
- Python/Shapely validation.

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

## Important accuracy warning

The marketing floor plan explicitly says it is not to scale. The broker confirmed that the apartment entrance door is 1 metre wide. The current 1.52 cm/px scale is anchored to that door. All other dimensions remain estimates because the marketing floor plan explicitly says it is not to scale.

Do not use the current measurements for final purchase decisions where small clearances matter.

## Data model

- `data/apartment.json`: building geometry, spaces, walls, doors, windows, single-door-anchored estimated scale;
- `data/fixed-fixtures.json`: fitted kitchen and other permanent elements;
- `data/furniture.json`: agent-controlled furniture layouts;
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
