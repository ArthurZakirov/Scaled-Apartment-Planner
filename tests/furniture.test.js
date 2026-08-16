import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import { evaluationSummary, findLayoutForArrangement, findLayoutForSelection, formatEvaluationReason, layoutsForDesk, normalizeScenarioId, recommendAlternativeLayouts, resolveScenarioData, validLayoutsForDesk } from '../src/furniture.js';

const catalog = JSON.parse(await readFile(new URL('../data/furniture-catalog.json', import.meta.url), 'utf8'));
const scenarios = JSON.parse(await readFile(new URL('../data/layout-scenarios.json', import.meta.url), 'utf8'));
const evaluations = JSON.parse(await readFile(new URL('../data/scenario-evaluations.json', import.meta.url), 'utf8'));

test('browser resolves all 23040 product, orientation, desk, fridge-model, and fridge-placement scenarios', () => {
  const furniture = resolveScenarioData(scenarios, catalog);
  assert.equal(furniture.layouts.length, 23040);
  assert.equal(new Set(furniture.layouts.map((layout) => layout.id)).size, 23040);
});

test('current bed resolves independently from estimated new beds', () => {
  const furniture = resolveScenarioData(scenarios, catalog);
  const layout = furniture.layouts.find((item) => item.selection.bedVariantId === 'current-bed-90');
  const bed = layout.objects.find((object) => object.type === 'bed');
  assert.equal(bed.templateId, 'current-bed');
  assert.deepEqual(bed.dimensionsCm, { width: 111, depth: 204 });
  assert.deepEqual(bed.mattressCm, { width: 90, depth: 200 });
  assert.equal(bed.headEdge, 'negativeDepth');
});

test('estimated new bed and real modular PAX dimensions resolve', () => {
  const furniture = resolveScenarioData(scenarios, catalog);
  const layout = furniture.layouts.find((item) => item.selection.bedVariantId === 'new-bed-140' && item.selection.paxVariantId === 'pax-200');
  const bed = layout.objects.find((object) => object.type === 'bed');
  const pax = layout.objects.find((object) => object.type === 'wardrobe');
  assert.deepEqual(bed.dimensionsCm, { width: 156, depth: 209 });
  assert.deepEqual(bed.mattressCm, { width: 140, depth: 200 });
  assert.match(bed.estimateNote, /8 cm/);
  assert.equal(pax.dimensionsCm.width, 199.6);
  assert.equal(pax.modules.length, 2);
  assert.equal(pax.requiresAnchoring, true);
  assert.equal(pax.accessLabel, 'offener Kleiderzugriff');
});

test('owned bedside cabinet is present with user-provided dimensions', () => {
  const furniture = resolveScenarioData(scenarios, catalog);
  for (const layout of furniture.layouts) {
    const cabinet = layout.objects.find((object) => object.type === 'storage');
    assert.deepEqual(cabinet.dimensionsCm, { width: 43, depth: 57.5, height: 54 });
    assert.equal(cabinet.confidence, 'user_provided_dimensions');
    assert.equal(cabinet.accessLabel, 'Schubladen');
    assert.equal(cabinet.accessDepthCm, 35);
  }
});

test('KESSER and Bosch are mutually exclusive fridge alternatives with independent placements', () => {
  const furniture = resolveScenarioData(scenarios, catalog);
  assert.deepEqual(
    new Set(furniture.layouts.map((layout) => layout.selection.minifridgePlacementId)),
    new Set(['endcap-extension', 'kitchen-back-wall', 'kitchen-balcony-wall'])
  );
  assert.deepEqual(
    new Set(furniture.layouts.map((layout) => layout.selection.fridgeVariantId)),
    new Set(['kesser-minifridge-40', 'bosch-kgn36vict-60'])
  );
  for (const layout of furniture.layouts.filter((layout) => layout.selection.fridgeVariantId === 'kesser-minifridge-40')) {
    const fridge = layout.objects.find((object) => object.type === 'appliance');
    assert.deepEqual(fridge.dimensionsCm, { width: 40, depth: 43, height: 57 });
    assert.equal(fridge.accessLabel, 'Kühlschranktür');
    assert.equal(fridge.accessDepthCm, 40);
  }
  for (const layout of furniture.layouts.filter((layout) => layout.selection.fridgeVariantId === 'bosch-kgn36vict-60')) {
    const appliances = layout.objects.filter((object) => object.type === 'appliance');
    assert.equal(appliances.length, 1);
    const fridge = appliances[0];
    assert.deepEqual(fridge.dimensionsCm, { width: 60, depth: 72, height: 186 });
    assert.deepEqual(fridge.bodyDimensionsCm, { width: 60, depth: 66.5, height: 186 });
    assert.equal(fridge.accessDepthCm, 55);
    assert.equal(fridge.doorSweepRadiusCm, 65.5);
  }
});

test('PAX height is not a 2D scenario axis and all five arrangements resolve', () => {
  const furniture = resolveScenarioData(scenarios, catalog);
  const paxVariants = new Set();
  const arrangements = new Set();
  for (const layout of furniture.layouts) {
    arrangements.add(layout.arrangementId);
    paxVariants.add(layout.objects.find((object) => object.type === 'wardrobe').variantId);
  }
  assert.deepEqual(paxVariants, new Set(['pax-100', 'pax-150', 'pax-175', 'pax-200']));
  assert.deepEqual(arrangements, new Set(['divider', 'bath-wall-bed-shifted', 'bath-wall-both-rotated', 'east-wall-wardrobe', 'kitchen-wall-wardrobe']));
  assert.deepEqual(new Set(furniture.layouts.map((layout) => layout.selection.deskPlacementId)), new Set(['upper-loggia-corner', 'lower-balcony-corner', 'living-room-centre', 'balcony-between-doors', 'kitchen-balcony-corner']));
});

test('legacy low-height scenario links map to their width-only counterpart', () => {
  const canonical = 'scenario-bath-wall-both-rotated-current-bed-90-pax-200-quick-150-150';
  const legacy = canonical.replace('pax-200', 'pax-200-low');
  const furniture = resolveScenarioData(scenarios, catalog, legacy);
  assert.equal(normalizeScenarioId(legacy), canonical);
  assert.equal(furniture.activeLayoutId, canonical);
});

test('legacy MALM scenario links map to estimated new-bed widths', () => {
  const legacy = 'scenario-malm-140-pax-200-quick-150-150';
  assert.equal(normalizeScenarioId(legacy), 'scenario-new-bed-140-pax-200-quick-150-150');
});

test('PAX access depth changes without changing another scenario axis', () => {
  const furniture = resolveScenarioData(scenarios, catalog);
  const legacyId = 'scenario-new-bed-90-pax-200-quick-150-150';
  const legacy = furniture.layouts.find((layout) => layout.id === legacyId);
  assert.equal(legacy.selection.paxAccessDepthCm, 45);
  for (const depth of [0, 30, 60]) {
    const alternate = furniture.layouts.find((layout) => layout.id === `${legacyId}-pax-access-${depth}`);
    assert.ok(alternate);
    assert.deepEqual(
      { ...alternate.selection, paxAccessDepthCm: 45 },
      legacy.selection
    );
  }
});

test('each furniture control changes only its own scenario axis', () => {
  const resolved = resolveScenarioData(scenarios, catalog);
  const activeLayout = resolved.layouts.find((layout) => layout.id === resolved.activeLayoutId);
  const alternateByAxis = {
    arrangementId: 'bath-wall-both-rotated',
    bedVariantId: 'new-bed-120',
    paxVariantId: 'pax-175',
    paxAccessDepthCm: 30,
    deskPlacementId: 'lower-balcony-corner',
    minifridgePlacementId: 'kitchen-back-wall',
    fridgeVariantId: 'bosch-kgn36vict-60'
  };

  for (const [axis, value] of Object.entries(alternateByAxis)) {
    const target = findLayoutForSelection(resolved.layouts, activeLayout, { [axis]: value });
    assert.ok(target, `${axis} alternate is present in the unchanged scenario matrix`);
    assert.equal(target.selection[axis], value);
    assert.deepEqual(
      { ...target.selection, [axis]: activeLayout.selection[axis] },
      activeLayout.selection,
      `${axis} changed another selection axis`
    );
  }
});

test('evaluated-invalid axis options remain selectable for visual inspection', () => {
  const resolved = resolveScenarioData(scenarios, catalog);
  const layouts = validLayoutsForDesk(resolved.layouts, evaluations, 'quick-150-150');
  const activeLayout = layouts.find((layout) => layout.id === resolved.activeLayoutId);
  const target = findLayoutForSelection(layouts, activeLayout, { arrangementId: 'bath-wall-both-rotated' });
  assert.ok(target);
  const evaluation = evaluations.results.find((item) => item.id === target.id);
  assert.equal(evaluation.valid, false);
  assert.ok(evaluationSummary(evaluation));
});

test('changing an arrangement selects its compatible desk placement instead of disabling existing layouts', () => {
  const resolved = resolveScenarioData(scenarios, catalog);
  const validLayouts = validLayoutsForDesk(resolved.layouts, evaluations, 'quick-150-150');
  const eastWall = validLayouts.find((layout) => layout.id === 'scenario-east-wall-wardrobe-new-bed-90-pax-150-quick-150-150-living-room-centre-pax-access-0-fridge-kitchen-back-wall');
  const divider = findLayoutForArrangement(validLayouts, eastWall, 'divider');
  assert.ok(divider);
  assert.equal(divider.selection.deskPlacementId, 'upper-loggia-corner');
  assert.deepEqual(
    { ...divider.selection, arrangementId: eastWall.selection.arrangementId, deskPlacementId: eastWall.selection.deskPlacementId },
    eastWall.selection
  );
});

test('changing an arrangement preserves the selected PAX access reserve even when evaluation flags it', () => {
  const resolved = resolveScenarioData(scenarios, catalog);
  const validLayouts = validLayoutsForDesk(resolved.layouts, evaluations, 'quick-150-150');
  const divider = validLayouts.find((layout) => layout.id === 'scenario-new-bed-90-pax-200-quick-150-150-lower-balcony-corner');
  const rotated = findLayoutForArrangement(validLayouts, divider, 'bath-wall-both-rotated');
  assert.ok(rotated);
  assert.equal(rotated.selection.arrangementId, 'bath-wall-both-rotated');
  assert.equal(rotated.selection.paxAccessDepthCm, 45);
  assert.equal(rotated.selection.deskPlacementId, 'lower-balcony-corner');
});

test('user-facing bedroom layouts contain valid and invalid evaluations and preserve the desk', () => {
  const furniture = resolveScenarioData(scenarios, catalog);
  const layouts = layoutsForDesk(furniture.layouts, 'quick-150-150');
  const validIds = new Set(evaluations.results.filter((result) => result.valid).map((result) => result.id));
  assert.equal(layouts.length, 5760);
  assert.ok(layouts.some((layout) => validIds.has(layout.id)));
  assert.ok(layouts.some((layout) => !validIds.has(layout.id)));
  assert.ok(layouts.every((layout) => layout.selection.deskVariantId === 'quick-150-150'));
  assert.deepEqual(new Set(layouts.map((layout) => layout.selection.deskPlacementId)), new Set(['upper-loggia-corner', 'lower-balcony-corner', 'living-room-centre', 'balcony-between-doors', 'kitchen-balcony-corner']));
});

test('every invalid scenario has a concrete reason for the adviser', () => {
  const invalid = evaluations.results.filter((result) => !result.valid);
  assert.ok(invalid.length > 0);
  assert.ok(invalid.every((result) => result.reasons.length > 0));
  assert.ok(invalid.every((result) => evaluationSummary(result)));
});

test('PAX wall-limit conflicts state the dimension and corrective action', () => {
  const evaluation = evaluations.results.find((result) =>
    result.arrangementId === 'east-wall-wardrobe'
    && result.id.includes('pax-200')
    && result.reasons.some((reason) => reason.includes('fixed balcony-wall segment'))
  );
  assert.equal(evaluationSummary(evaluation), 'PAX 200 cm > Wand 167 cm');
  const wallReason = evaluation.reasons.find((reason) => reason.includes('fixed balcony-wall segment'));
  assert.match(formatEvaluationReason(wallReason), /Wähle.*PAX 150 cm/);
});

test('invalid layouts receive at most three valid nearby alternatives', () => {
  const furniture = resolveScenarioData(scenarios, catalog);
  const layouts = layoutsForDesk(furniture.layouts, 'quick-150-150');
  const active = layouts.find((layout) => layout.id === 'scenario-east-wall-wardrobe-new-bed-90-pax-200-quick-150-150-living-room-centre');
  const alternatives = recommendAlternativeLayouts(layouts, evaluations, active, 3);
  const validIds = new Set(evaluations.results.filter((result) => result.valid).map((result) => result.id));
  assert.ok(alternatives.length > 0 && alternatives.length <= 3);
  assert.ok(alternatives.every((candidate) => validIds.has(candidate.layout.id)));
  assert.ok(alternatives.every((candidate) => candidate.changedAxes.length > 0));
  assert.ok(alternatives.every((candidate, index) => index === 0 || candidate.changedAxes.length >= alternatives[index - 1].changedAxes.length));
});

test('query-selected scenario becomes active without mutating stored data', () => {
  const selected = scenarios.scenarios[5].id;
  const furniture = resolveScenarioData(scenarios, catalog, selected);
  assert.equal(furniture.activeLayoutId, selected);
  assert.equal(scenarios.activeScenarioId, 'scenario-new-bed-90-pax-200-quick-150-150');
});
