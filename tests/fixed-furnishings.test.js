import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const furnishings = JSON.parse(await readFile(new URL('../data/fixed-furnishings.json', import.meta.url), 'utf8'));
const scenarios = JSON.parse(await readFile(new URL('../data/layout-scenarios.json', import.meta.url), 'utf8'));

test('the original kitchen table keeps two fixed chairs on its right-hand long edge', () => {
  assert.equal(furnishings.furnishings.length, 2);
  assert.deepEqual(
    furnishings.furnishings.map(({ id, type, shape, openSide, anchorFixtureId }) => ({
      id, type, shape, openSide, anchorFixtureId
    })),
    [
      {
        id: 'kitchen-chair-upper',
        type: 'dining_chair',
        shape: 'side_chair',
        openSide: 'west',
        anchorFixtureId: 'kitchen-return'
      },
      {
        id: 'kitchen-chair-lower',
        type: 'dining_chair',
        shape: 'side_chair',
        openSide: 'west',
        anchorFixtureId: 'kitchen-return'
      }
    ]
  );

  const [upper, lower] = furnishings.furnishings;
  assert.equal(upper.x, lower.x);
  assert.ok(upper.y + upper.depthPx < lower.y);
});

test('fixed kitchen chairs are not duplicated into furniture scenarios', () => {
  for (const scenario of scenarios.scenarios) {
    assert.ok(scenario.objects.every((object) => !object.id.startsWith('kitchen-chair-')));
  }
});
