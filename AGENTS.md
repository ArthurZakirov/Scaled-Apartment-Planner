# Agent rules

## Non-negotiable geometry rules

- Never edit, overwrite, crop in place, paint over, mask, retouch, or otherwise mutate `the immutable source URL in `data/apartment.json``.
- Treat the source image only as an immutable calibration reference.
- The normal application must render from structured JSON and SVG geometry, never from the source image.
- Keep building structure, fixed fixtures, and loose furniture in separate data files.
- Do not remove source furniture by covering it with white shapes. Omit it from the reconstructed vector model instead.
- Do not simplify the apartment into a rectangle. Preserve the sloped walls, corners, door openings, loggia, and balcony.
- Preserve the calibrated inset interior boundary along the Loggia; wall centerlines and visual stroke thicknesses may be refined independently and are not interchangeable with the usable-room boundary.
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
- The bedroom controls must expose only geometrically valid combinations. Keep invalid scenarios in generated evaluation data for diagnostics, but never make them selectable in the user-facing planner.
- `ikea-pax-divider` varies between real modular widths of 149.6, 174.6, and 199.6 cm.
- PAX height is deliberately not a 2D scenario axis. The purchasable 201.2 and 236.4 cm heights share the same footprint and both require anchoring.
- The bathroom-facing short end of PAX and its cross-axis offset are invariant; width changes move only the free end toward or away from the bed.
- A transverse PAX is never labeled safe without an engineered support solution. Bathroom-wall-parallel concepts are only mounting candidates until the actual wall and fasteners are verified.
- `sleeping-bed` can use the current 90 × 200 cm mattress/111 × 204 cm frame or an estimated new bed for 90, 120, 140, 160, and 180 cm mattress widths while keeping its wall-side edge fixed.
- In `bath-wall-both-rotated`, preserve the 20 cm headboard-to-wall strip created by the recessed bedroom-Loggia door reveal; this replaces direct wall contact for that orientation.
- Bedroom controls preserve the active VERNAL desk variant; changing bed, mattress, PAX, orientation, or desk position must not change the desk size.
- Each bedroom selector changes only its own axis. If the exact combination is invalid, disable that option; never silently change orientation, bed, PAX, or another furniture choice to make it fit.
- `owned-bedside-cabinet` is the user's 57.5 × 43 × 54 cm cabinet. It follows the bed orientation, keeps a 2 cm planning gap to the bed, and requires a clear 35 cm drawer-access strip inside the apartment.
- No furniture footprint or door swing may enter the scenario-selected 0/30/45/60 cm PAX opening/access strip. This includes the bed, cabinet, and desk; footprint non-overlap alone is not sufficient for a usable scenario. The 45 cm option is the default and keeps legacy URLs suffix-free.
- After each geometry change, inspect both `/calibration/` and `/` yourself and iterate until the result is physically possible, geometrically consistent, and practically usable without obvious common-sense contradictions.
- Preserve the in-plan orientation markers: bed head/pillow edge, open PAX access edge, and cabinet drawer front must follow the same local negative-depth edge used by geometry.
- The VERNAL desk has two independent anchors. Its upper position touches the Loggia/east walls; its lower position touches the south wall and only the short segment of the reconstructed southeast wall step, not a continuous long right wall.
- Reserve and validate a visible 60 × 60 cm chair/work zone inside every VERNAL cutout. It must remain inside the apartment and clear of fixed fixtures and other furniture.
- Apply the 60 cm desk-to-kitchen passage minimum only to the lower desk position; it is not a global furniture-spacing rule.
- Preserve the southeast interior step `[507,263] → [507,514] → [493,514] → [493,527]`; it represents the visible structural projection beside the lower balcony door.
- Treat every `kind: interior` wall as a solid formed from its centerline and full `thicknessPx`; no loose furniture footprint may overlap that solid.
- An individual loggia or balcony door may be blocked, but never both doors in the same access group.

## Editing workflow

1. Inspect `data/apartment.json`, `data/fixed-fixtures.json`, `data/furniture-catalog.json`, `data/scenario-matrix.json`, and `data/layout-constraints.json`.
2. Make the smallest structured-data change needed.
3. Run `npm run generate:scenarios` for furniture-catalog or matrix changes.
4. Run `npm run validate`.
5. Open `/calibration/` and compare the overlay with the original image.
6. Open `/` and verify the resulting layout, ranked navigation, metrics, and door-status panel.
7. Record new assumptions or ambiguities in `docs/reconstruction-notes.md`.
