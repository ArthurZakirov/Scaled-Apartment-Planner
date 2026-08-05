# Scaled Apartment Planner

A structured, agent-controlled apartment planner for Wohnung 264. The project reconstructs the non-rectangular floor plan as SVG geometry and keeps the original source image only as an immutable calibration reference.

## Current state

The first experiment includes:

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

The apartment entrance door is the confirmed 100 cm scale anchor. All other dimensions remain estimates because the marketing floor plan explicitly states that it is not to scale.

## Data model

- `data/apartment.json`: building geometry, spaces, walls, doors, windows, and estimated scale;
- `data/fixed-fixtures.json`: fitted kitchen and permanent elements;
- `data/furniture.json`: agent-controlled furniture layouts;
- `data/layout-constraints.json`: door and clearance policies;
- `AGENTS.md`: binding rules for Codex and other coding agents.
