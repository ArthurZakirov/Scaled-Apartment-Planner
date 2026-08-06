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

The catalog contains the user's current 111 × 204 cm bed with a 90 × 200 cm mattress, three MALM mattress sizes, three modular PAX widths, and four VERNAL L-desk variants. Their Cartesian product is generated as 48 explicit scenarios. Each scenario is checked for containment, furniture overlap, mandatory door access, at least one usable loggia door, and at least one usable balcony door.

The browser reads a generated evaluation file and navigates only through valid scenarios, ranked by a transparent planning score. Invalid scenarios remain in the generated data for diagnosis and regression testing.

The ranking is an exploration aid, not a purchase recommendation: the approximate source scale can make small reported gaps unreliable.

### Furniture anchor invariants

- MALM width changes preserve the wall-side external frame edge. The free edge moves toward or away from PAX, so a narrower bed creates a larger signed bed-to-PAX gap.
- PAX width changes preserve the bathroom-facing short end and its perpendicular offset from the bathroom wall. Only the free end toward the bed moves.
- VERNAL dimensions are resolved from a fixed top-right wall-contact corner. Its top edge stays on the loggia-side wall and its right edge stays on the window/east wall for every variant.
- Automated tests compare these projected edges and wall-contact coordinates across the complete variant matrix.

## Default layout experiment

### IKEA PAX divider

- Real modular footprint: 199.6 × 58 cm (two 99.8 cm corpuses).
- Height: 236.4 cm.
- Used as a visual divider rather than a structural wall.
- Every PAX scenario carries an explicit anchoring warning.

### IKEA MALM bed

- Mattress: 140 × 200 cm.
- Actual outer footprint: 156 × 209 cm.
- Rotated 90° relative to the original suggested bed orientation.

### Vernal L-shaped desk

- Outer extent: 180 × 150 cm.
- Main top depth: 75 cm.
- Return depth: 70 cm.
- The initial position intentionally occupies the corner at the living-room loggia door and upper balcony door.
- The lower balcony door and bedroom-side loggia door remain clear in the current geometric check.

## Next high-value measurements

Before final purchase decisions, collect at least three independent real measurements:

1. identify the exact 100 cm door;
2. measure one long interior wall;
3. measure the clear width between the loggia/balcony corner and the opposing wall or partition.

These measurements would allow a least-squares affine calibration and reveal whether the marketing image is distorted differently along different axes.
