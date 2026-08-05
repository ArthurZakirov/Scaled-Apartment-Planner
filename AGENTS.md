# Agent rules

## Non-negotiable geometry rules

- Never edit, overwrite, crop in place, paint over, mask, retouch, or otherwise mutate `the immutable source URL in `data/apartment.json``.
- Treat the source image only as an immutable calibration reference.
- The normal application must render from structured JSON and SVG geometry, never from the source image.
- Keep building structure, fixed fixtures, and loose furniture in separate data files.
- Do not remove source furniture by covering it with white shapes. Omit it from the reconstructed vector model instead.
- Do not simplify the apartment into a rectangle. Preserve the sloped walls, corners, door openings, loggia, and balcony.
- Geometry correctness comes before styling.
- A successful build is not visual validation. Changes to the apartment geometry must be checked in `/calibration/` against the source image.
- Never silently convert estimated dimensions into exact dimensions. Preserve `confidence`, `status`, and source notes.
- The apartment entrance door is the confirmed 100 cm scale anchor. Dimensions elsewhere remain approximate because the source explicitly states that it is not to scale.
- Use the full external footprint of products. For example, the MALM 140 × 200 mattress uses a 156 × 209 cm bed-frame footprint.
- Do not add furniture forms to the user-facing app. Furniture is controlled by editing structured data or, later, through CLI/MCP tools.
- Preserve the policy that at least one balcony door and at least one loggia door remain usable.
- Run `npm run validate` before committing layout changes.

## Current intended layout experiment

- `ikea-pax-divider` acts as a 200 × 58 cm room divider.
- `ikea-malm-bed` is rotated 90° relative to the bed orientation in the source illustration.
- `vernal-l-desk` is intentionally placed in the upper-right living-area corner.
- The desk may block `door-loggia-living` and `door-balcony-upper`.
- `door-loggia-bedroom` and `door-balcony-lower` must stay usable.

## Editing workflow

1. Inspect `data/apartment.json`, `data/fixed-fixtures.json`, `data/furniture.json`, and `data/layout-constraints.json`.
2. Make the smallest structured-data change needed.
3. Run `npm run validate`.
4. Open `/calibration/` and compare the overlay with the original image.
5. Open `/` and verify the resulting layout and door-status panel.
6. Record new assumptions or ambiguities in `docs/reconstruction-notes.md`.
