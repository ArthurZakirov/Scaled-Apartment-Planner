import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import { normalizeScenarioId, resolveScenarioData } from '../src/furniture.js';

const catalog = JSON.parse(await readFile(new URL('../data/furniture-catalog.json', import.meta.url), 'utf8'));
const scenarios = JSON.parse(await readFile(new URL('../data/layout-scenarios.json', import.meta.url), 'utf8'));

test('browser resolves all 72 product and orientation scenarios', () => {
  const furniture = resolveScenarioData(scenarios, catalog);
  assert.equal(furniture.layouts.length, 72);
  assert.equal(new Set(furniture.layouts.map((layout) => layout.id)).size, 72);
});

test('current bed resolves independently from MALM', () => {
  const furniture = resolveScenarioData(scenarios, catalog);
  const layout = furniture.layouts.find((item) => item.selection.bedVariantId === 'current-bed-90');
  const bed = layout.objects.find((object) => object.type === 'bed');
  assert.equal(bed.templateId, 'current-bed');
  assert.deepEqual(bed.dimensionsCm, { width: 111, depth: 204 });
  assert.deepEqual(bed.mattressCm, { width: 90, depth: 200 });
});

test('active scenario uses external MALM and real modular PAX dimensions', () => {
  const furniture = resolveScenarioData(scenarios, catalog);
  const layout = furniture.layouts.find((item) => item.selection.bedVariantId === 'malm-140' && item.selection.paxVariantId === 'pax-200');
  const bed = layout.objects.find((object) => object.type === 'bed');
  const pax = layout.objects.find((object) => object.type === 'wardrobe');
  assert.deepEqual(bed.dimensionsCm, { width: 156, depth: 209, height: 100 });
  assert.equal(pax.dimensionsCm.width, 199.6);
  assert.equal(pax.modules.length, 2);
  assert.equal(pax.requiresAnchoring, true);
});

test('owned bedside cabinet is present with user-provided dimensions', () => {
  const furniture = resolveScenarioData(scenarios, catalog);
  for (const layout of furniture.layouts) {
    const cabinet = layout.objects.find((object) => object.type === 'storage');
    assert.deepEqual(cabinet.dimensionsCm, { width: 57.5, depth: 43, height: 54 });
    assert.equal(cabinet.confidence, 'user_provided_dimensions');
  }
});

test('PAX height is not a 2D scenario axis and all three arrangements resolve', () => {
  const furniture = resolveScenarioData(scenarios, catalog);
  const paxVariants = new Set();
  const arrangements = new Set();
  for (const layout of furniture.layouts) {
    arrangements.add(layout.arrangementId);
    paxVariants.add(layout.objects.find((object) => object.type === 'wardrobe').variantId);
  }
  assert.deepEqual(paxVariants, new Set(['pax-150', 'pax-175', 'pax-200']));
  assert.deepEqual(arrangements, new Set(['divider', 'bath-wall-bed-shifted', 'bath-wall-both-rotated']));
});

test('legacy low-height scenario links map to their width-only counterpart', () => {
  const canonical = 'scenario-bath-wall-both-rotated-current-bed-90-pax-200-quick-150-150';
  const legacy = canonical.replace('pax-200', 'pax-200-low');
  const furniture = resolveScenarioData(scenarios, catalog, legacy);
  assert.equal(normalizeScenarioId(legacy), canonical);
  assert.equal(furniture.activeLayoutId, canonical);
});

test('query-selected scenario becomes active without mutating stored data', () => {
  const selected = scenarios.scenarios[5].id;
  const furniture = resolveScenarioData(scenarios, catalog, selected);
  assert.equal(furniture.activeLayoutId, selected);
  assert.equal(scenarios.activeScenarioId, 'scenario-bath-wall-bed-shifted-current-bed-90-pax-175-quick-180-150');
});
