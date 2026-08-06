import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import { resolveScenarioData } from '../src/furniture.js';

const catalog = JSON.parse(await readFile(new URL('../data/furniture-catalog.json', import.meta.url), 'utf8'));
const scenarios = JSON.parse(await readFile(new URL('../data/layout-scenarios.json', import.meta.url), 'utf8'));

test('browser resolves all 48 product-variant scenarios', () => {
  const furniture = resolveScenarioData(scenarios, catalog);
  assert.equal(furniture.layouts.length, 48);
  assert.equal(new Set(furniture.layouts.map((layout) => layout.id)).size, 48);
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
  const active = furniture.layouts.find((layout) => layout.id === furniture.activeLayoutId);
  const bed = active.objects.find((object) => object.type === 'bed');
  const pax = active.objects.find((object) => object.type === 'wardrobe');
  assert.deepEqual(bed.dimensionsCm, { width: 156, depth: 209, height: 100 });
  assert.equal(pax.dimensionsCm.width, 199.6);
  assert.equal(pax.modules.length, 2);
  assert.equal(pax.requiresAnchoring, true);
});

test('query-selected scenario becomes active without mutating stored data', () => {
  const selected = scenarios.scenarios[5].id;
  const furniture = resolveScenarioData(scenarios, catalog, selected);
  assert.equal(furniture.activeLayoutId, selected);
  assert.equal(scenarios.activeScenarioId, 'scenario-malm-140-pax-200-stable-180-150');
});
