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

## Current layout scenario system

- `data/furniture-catalog.json` is the source of truth for product templates and verified external dimensions.
- `data/scenario-matrix.json` defines the current bed plus 3 MALM × 3 PAX × 4 VERNAL axes and common placement anchors.
- Run `npm run generate:scenarios` after editing the catalog or matrix; do not hand-edit generated scenario or evaluation files.
- The user-facing navigation includes only scenarios that satisfy mandatory geometry and door constraints.
- `ikea-pax-divider` varies between real modular widths of 149.6, 174.6, and 199.6 cm.
- The bathroom-facing short end of PAX and its cross-axis offset are invariant; width changes move only the free end toward or away from the bed.
- `ikea-malm-bed` can use the current 90 × 200 cm mattress/111 × 204 cm frame or MALM 140, 160, and 180 cm mattresses while keeping its wall-side edge fixed.
- The VERNAL desk is anchored by its top-right wall-contact corner; both wall-facing edges remain in contact for every desk size.
- `vernal-l-desk` is intentionally placed in the upper-right living-area corner.
- The desk may block `door-loggia-living` and `door-balcony-upper`.
- `door-loggia-bedroom` and `door-balcony-lower` must stay usable.

## Editing workflow

1. Inspect `data/apartment.json`, `data/fixed-fixtures.json`, `data/furniture-catalog.json`, `data/scenario-matrix.json`, and `data/layout-constraints.json`.
2. Make the smallest structured-data change needed.
3. Run `npm run generate:scenarios` for furniture-catalog or matrix changes.
4. Run `npm run validate`.
5. Open `/calibration/` and compare the overlay with the original image.
6. Open `/` and verify the resulting layout, ranked navigation, metrics, and door-status panel.
7. Record new assumptions or ambiguities in `docs/reconstruction-notes.md`.
