import assert from 'node:assert/strict';
import test from 'node:test';

import {
  DISPLAY_OPTIONS,
  allDisplayLayers,
  applyDisplayState,
  parseDisplayState,
  serializeDisplayState,
  setDisplayStateInUrl
} from '../src/display-filter.js';

test('display state defaults to every layer and omits the URL parameter', () => {
  const state = parseDisplayState(new URLSearchParams('scenario=example'));
  assert.deepEqual([...state], DISPLAY_OPTIONS.map((option) => option.id));
  assert.equal(serializeDisplayState(state), null);
});

test('display state serializes canonically and supports hiding everything', () => {
  const partial = new Set(['furniture', 'labels']);
  assert.equal(serializeDisplayState(partial), 'labels,furniture');
  assert.deepEqual(
    [...parseDisplayState(new URLSearchParams('display=labels,unknown,furniture'))],
    ['labels', 'furniture']
  );
  assert.equal(serializeDisplayState(allDisplayLayers(false)), 'none');
  assert.deepEqual([...parseDisplayState(new URLSearchParams('display=none'))], []);
});

test('changing display state preserves scenario and unrelated query parameters', () => {
  const original = new URL('https://example.test/?scenario=layout-42&debug=1');
  const updated = setDisplayStateInUrl(original, new Set(['doors']));
  assert.equal(updated.searchParams.get('scenario'), 'layout-42');
  assert.equal(updated.searchParams.get('debug'), '1');
  assert.equal(updated.searchParams.get('display'), 'doors');
  assert.equal(original.searchParams.has('display'), false);

  const restored = setDisplayStateInUrl(updated, allDisplayLayers());
  assert.equal(restored.searchParams.has('display'), false);
  assert.equal(restored.searchParams.get('scenario'), 'layout-42');
});

test('applying display state touches only the four presentation layers', () => {
  const layers = new Map([...DISPLAY_OPTIONS, { id: 'annotations', selector: '.layer-annotations' }].map((option) => [
    option.selector,
    {
      hidden: false,
      ariaHidden: null,
      classList: { toggle: (_name, hidden) => { layers.get(option.selector).hidden = hidden; } },
      setAttribute: (_name, value) => { layers.get(option.selector).ariaHidden = value; }
    }
  ]));
  const svg = { querySelector: (selector) => layers.get(selector) };

  applyDisplayState(svg, new Set(['labels', 'furniture']));

  assert.equal(layers.get('.layer-labels').hidden, false);
  assert.equal(layers.get('.layer-doors').hidden, true);
  assert.equal(layers.get('.layer-access-zones').hidden, true);
  assert.equal(layers.get('.layer-furniture').hidden, false);
  assert.equal(layers.get('.layer-annotations').hidden, false, 'calibration annotations remain untouched');
});
