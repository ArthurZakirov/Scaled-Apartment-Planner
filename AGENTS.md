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
- Use the full external footprint of products. Generic new beds currently use an explicit planning estimate of mattress width + 16 cm and 209 cm total length; never present this estimate as an exact product dimension.
- Do not add furniture forms to the user-facing app. Furniture is controlled by editing structured data or, later, through CLI/MCP tools.
- Preserve the hard grouped-door policy: every valid scenario must leave at least one balcony door and at least one loggia door usable.
- Run `npm run validate` before committing layout changes.

## Current layout scenario system

- `data/furniture-catalog.json` is the source of truth for product templates and verified external dimensions.
- `data/scenario-matrix.json` defines bed, PAX width, VERNAL, and orientation concepts with common placement anchors.
- Run `npm run generate:scenarios` after editing the catalog or matrix; do not hand-edit generated scenario or evaluation files.
- The bedroom controls may display invalid combinations so the user can understand why they fail; never label an invalid scenario as a valid proposal.
- `ikea-pax-divider` varies between real modular widths of 149.6, 174.6, and 199.6 cm.
- PAX height is deliberately not a 2D scenario axis. The purchasable 201.2 and 236.4 cm heights share the same footprint and both require anchoring.
- The bathroom-facing short end of PAX and its cross-axis offset are invariant; width changes move only the free end toward or away from the bed.
- A transverse PAX is never labeled safe without an engineered support solution. Bathroom-wall-parallel concepts are only mounting candidates until the actual wall and fasteners are verified.
- `sleeping-bed` can use the current 90 × 200 cm mattress/111 × 204 cm frame or an estimated new bed for 90, 120, 140, 160, and 180 cm mattress widths while keeping its wall-side edge fixed.
- Bedroom controls preserve the active VERNAL desk variant; changing bed, mattress, PAX, or orientation must not change the desk.
- `owned-bedside-cabinet` is the user's 57.5 × 43 × 54 cm cabinet. It follows the bed orientation and keeps a 2 cm planning gap to the bed.
- The VERNAL desk is anchored by its top-right wall-contact corner; both wall-facing edges remain in contact for every desk size.
- `vernal-l-desk` is intentionally placed in the upper-right living-area corner.
- An individual loggia or balcony door may be blocked, but never both doors in the same access group.

## Editing workflow

1. Inspect `data/apartment.json`, `data/fixed-fixtures.json`, `data/furniture-catalog.json`, `data/scenario-matrix.json`, and `data/layout-constraints.json`.
2. Make the smallest structured-data change needed.
3. Run `npm run generate:scenarios` for furniture-catalog or matrix changes.
4. Run `npm run validate`.
5. Open `/calibration/` and compare the overlay with the original image.
6. Open `/` and verify the resulting layout, ranked navigation, metrics, and door-status panel.
7. Record new assumptions or ambiguities in `docs/reconstruction-notes.md`.
