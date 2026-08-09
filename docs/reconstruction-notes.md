# Reconstruction notes

## Source facts

- Source image: the Augusta & Luca marketing floor plan for Wohnung 264.
- Declared living area in the source: 46.47 m².
- The source explicitly states that the illustration is non-binding and not to scale.
- The source also states that the shown fitted kitchen may differ from reality.
- Broker information supplied by the user: one door is 1 metre wide.

## Scale status

The broker confirmed that the apartment entrance door is the 100 cm reference. Its reconstructed leaf length is approximately 65.8 source pixels, producing 1.52 cm per source pixel.

The anchor identity is confirmed, but the resulting global scale remains low-confidence because the source explicitly states that it is not to scale. It is sufficient for experimenting with furniture footprints, but not for purchasing decisions that depend on a few centimetres of clearance.

## Coordinate system

Geometry is stored in source-image crop pixels. The crop is:

- x: 390 px
- y: 350 px
- width: 670 px
- height: 590 px

The immutable full source image remains 1753 × 1240 px. The calibration route places the full image at `(-390, -350)` beneath the SVG geometry.

## Reconstructed structural elements

The first pass contains:

- non-rectangular interior envelope;
- sloped north-west exterior wall;
- bathroom partitions and door;
- entrance door and flur/kitchen partition;
- two loggia access doors;
- two balcony doors;
- loggia and balcony outlines;
- continuous straight loggia edge at the neighbouring-loggia boundary;
- thick, inward-stepped flur/garderobe wall that prevents a direct turn into the kitchen;
- right-angled flur wall axis and garderobe return, perpendicular to the entrance-side wall;
- rectangular garderobe profile reconstructed from one parametric baseline, a fixed depth, and one derived right-angle end cap;
- approximate fitted-kitchen footprint;
- approximate south kitchen window and balcony glazing.

The structural model intentionally excludes the marketing illustration's bed, sofa, table, and other loose furniture.

## Geometry safeguards

- Parametric wall profiles are stored in `data/apartment.json`; their parallel side, perpendicular cap, and niche polygon are derived rather than edited independently.
- Declarative cross-project constraints live in `data/geometry-rules.json`.
- The validator reports measured angles, endpoint gaps, point-to-wall distances, and wall-to-fixture clearances.
- Critical reconstructed geometry uses strict tolerances; estimated source relationships may declare a wider tolerance that reflects the marketing plan's uncertainty.
- Automated negative tests verify that skewed walls, disconnected jambs, and kitchen overlaps fail validation.

## Known ambiguities

- Which door is exactly 100 cm wide.
- Exact wall thicknesses.
- Exact boundary between counted living area, loggia, and balcony.
- Some window spans in the sloped exterior wall.
- Exact fitted-kitchen cabinet geometry.
- The source is a marketing illustration and may contain local distortion.

## Product variants and scenario matrix

The catalog contains the user's current 111 × 204 cm bed with a 90 × 200 cm mattress, the user's 57.5 × 43 × 54 cm bedside cabinet, the existing KESSER minifridge with a 40 × 43 cm footprint and 57 cm height, five estimated new-bed footprints for 90, 120, 140, 160, and 180 cm mattresses, three modular PAX widths, and four VERNAL L-desk contexts. New-bed footprints assume 8 cm of frame on each mattress side and 9 cm additional total length, based on the previously verified 140 cm reference footprint; these are estimates, not product specifications. In the divider arrangement the cabinet occupies the audited room-corner position `[290,160]` at 144°, next to both 90 cm bed options and outside the bathroom; the other concepts continue to derive it from the bed with a 2 cm planning gap. A reserved 35 cm operating strip keeps the drawers usable. Configurations where it cannot fit or open remain invalid instead of hiding the cabinet. PAX height is purchase metadata rather than a 2D scenario axis because both available heights have the same footprint. Three bedroom orientation concepts, two independent desk positions, four selectable PAX access reserves, and two minifridge placements produce 3,456 explicit scenarios. The lower desk position is anchored to the reconstructed southeast wall step rather than a fictitious square corner. Each scenario is checked for containment, furniture overlap, crossing to the forbidden bathroom side of interior walls, fixed-kitchen clearance, a 60 × 60 cm desk work zone, mandatory door access, furniture operating zones, at least one usable loggia door, and at least one usable balcony door.

The minifridge placements are derived from `profile-garderobe`, not stored as unrelated absolute coordinates. Placement A continues the free end cap and points the marked door edge away from the profile. Placement B places the refrigerator back on the actual kitchen-side longitudinal wall, 150 cm from the profile start, where its full 40 cm operating zone fits between the estimated sink and kitchen return. Both the 40 × 43 cm footprint and the operating zone must remain strictly inside the apartment and clear of fixed kitchen fixtures, doors, bathroom, interior walls, and every loose-furniture footprint. Because the source plan is not to scale, these clearances must be checked on site before final installation.

The transverse divider remains a geometric experiment only because IKEA requires PAX to be wall anchored. A short-end-only attachment is not treated as equivalent to the documented rear wall mounting. Bathroom-wall-parallel concepts are marked as mounting candidates, not as verified installations; the actual wall substrate, fasteners, permitted drilling, and wardrobe access clearance must be confirmed before purchase.

The open wardrobe edge is rendered explicitly. The planner reports the bed-to-PAX gap as an access proxy: 60 cm or more is shown as good, 45–60 cm as tight, and less than 45 cm as too tight. These thresholds remain planning heuristics because the source drawing is not to scale.

The PAX opening has a user-selected 0, 30, 45, or 60 cm geometric access strip; 45 cm is the legacy/default value and 0 cm creates no strip beyond the PAX footprint. A scenario is invalid if any other furniture footprint intersects the selected strip, even when the furniture footprints themselves do not overlap. This catches the previous common-sense failure where a bed only 4.1 cm from the open PAX was labeled geometrically valid at larger reserved depths while still permitting open or sliding-door planning without an extra strip. Depending on the orientation, the cabinet moves to the free bed end or another corner-side position; arrangements where the bed blocks the selected access reserve remain diagnostic-only.

Furniture orientation is visible in the vector plan: pillows and a head label mark the bed head, an outward arrow marks the open PAX clothing-access side, and another outward arrow marks the cabinet drawer front. These indicators rotate with their furniture footprints.

Loggia access is a hard grouped constraint: a scenario is invalid as soon as both loggia door-swing areas are blocked. The same grouped rule applies to the two balcony doors. Neither rule relies on one permanently preferred door.

Safety research references:

- IKEA PAX 50 × 58 × 201 product page and wall-mounting requirement: https://www.ikea.com/de/de/p/pax-korpus-kleiderschrank-weiss-70458217/
- IKEA PAX 100 × 58 × 201 product page and wall-mounting requirement: https://www.ikea.com/de/de/p/pax-korpus-kleiderschrank-weiss-70458203/
- IKEA PAX assembly instructions: https://www.ikea.com/de/de/assembly_instructions/pax-korpus-kleiderschrank-weiss__AA-1289393-10-2.pdf
- IKEA wall-anchoring guide: https://www.ikea.com/de/de/files/pdf/1a/98/1a987529/bf_leitfaden_wandverankerung_07-2026_online.pdf
- US EPA guidance on cooking-generated indoor particles and range-hood use: https://www.epa.gov/indoor-air-quality-iaq/sources-indoor-particulate-matter-pm

The browser reads a generated evaluation file and exposes the bedroom dimensions through dedicated controls. It keeps the selected VERNAL desk size fixed while bed type, mattress width, PAX width, bedroom orientation, desk position, and minifridge placement change independently. Only geometrically valid combinations are selectable; impossible choices are visibly disabled, while invalid scenarios remain in generated data solely for diagnostics and regression tests.

Controls are axis-stable: selecting a mattress width never changes the orientation or PAX width, and selecting a PAX width never changes the bed or orientation. An invalid exact combination is disabled. Legacy links to invalid combinations fall back within the same orientation before considering another layout concept.

For the fully rotated arrangement, the current bed and estimated 90 cm and 120 cm beds retain headboard-wall contact and use calibrated along-wall offsets of 12 px, 9 px, and 31 px respectively so the correctly hinged bedroom Loggia-door swing remains clear. Wider beds do not fit this orientation under the current hard constraints.

The bedroom Loggia door is hinged at the upper endpoint `[352, 177]`; its leaf closes toward `[386, 220]` and swings inward toward `[309, 211]`. This matches the opposite hinge shown in the reference instead of the earlier reversed reconstruction.

The physical photo and the white rectangle in the source plan show that this door is recessed in a reveal. The model records a 20 cm reveal depth and renders it as a white outlined strip. In the fully rotated arrangement, the bed headboard is therefore held 20 cm off the wall so the open leaf can occupy that strip; the door-swing polygon remains unchanged and still participates in collision checks.

Pixel sampling perpendicular to the bedroom–Loggia wall suggests a dark wall band of approximately 26 source pixels. That stroke width is a visual calibration estimate, not a planning invariant. The authoritative planning geometry is the inset `space-main` boundary through `[290,133]`, `[333,192]`, `[384,263]`, and `[507,263]`; visual wall centerlines and thicknesses may be refined without moving it. The desk wall-contact anchor follows the corrected horizontal inner face at `y=263`.

The ranking is an exploration aid, not a purchase recommendation: the approximate source scale can make small reported gaps unreliable.

### Furniture anchor invariants

- New-bed width changes preserve the wall-side external frame edge. The free edge moves toward or away from PAX, so a narrower bed creates a larger signed bed-to-PAX gap.
- PAX width changes preserve the bathroom-facing short end and its perpendicular offset from the bathroom wall. Only the free end toward the bed moves.
- VERNAL dimensions are resolved from one of two fixed anchors. The upper position touches the Loggia-side and east walls; the lower position touches the south wall and only the short inner face of the reconstructed southeast wall step.
- Automated tests compare these projected edges and wall-contact coordinates across the complete variant matrix.

## Default layout experiment

### IKEA PAX divider

- Real modular footprint: 199.6 × 58 cm (two 99.8 cm corpuses).
- Height is selected separately at purchase and does not create another 2D layout.
- Used as a visual divider rather than a structural wall.
- Every PAX scenario carries an explicit anchoring warning.

### Estimated new bed

- Selectable mattresses: 90, 120, 140, 160, and 180 × 200 cm.
- Estimated outer footprint: mattress width + 16 cm, total length 209 cm.
- Rotated 90° relative to the original suggested bed orientation.

### Vernal L-shaped desk

- Outer extent: 180 × 150 cm.
- Main top depth: 75 cm.
- Return depth: 70 cm.
- The upper position intentionally occupies the corner at the living-room loggia door and upper balcony door.
- The lower position contacts the south wall and only the short face of the original southeast wall step, not a continuous long right wall. It blocks the lower balcony door while the upper balcony door remains free.
- A 60 × 60 cm chair/work zone is derived from each desk's handedness and rotation and must remain inside the apartment without intersecting fixed fixtures or loose furniture.
- A local 60 cm passage minimum applies between the lower desk footprint and the fixed kitchen. The current lower variants leave approximately 52.2, 42.2, or 22.2 cm and are therefore retained for diagnostics but rejected as practical layouts.

## Next high-value measurements

Before final purchase decisions, collect at least three independent real measurements:

1. identify the exact 100 cm door;
2. measure one long interior wall;
3. measure the clear width between the loggia/balcony corner and the opposing wall or partition.

These measurements would allow a least-squares affine calibration and reveal whether the marketing image is distorted differently along different axes.
