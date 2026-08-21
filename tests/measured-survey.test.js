import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const survey = JSON.parse(await readFile(new URL('../data/measured-survey.json', import.meta.url), 'utf8'));

test('measured survey preserves the verified bedroom dimensions', () => {
  const bedroom = survey.measuredAreas.find((area) => area.id === 'sleeping-area');
  assert.equal(bedroom.widthCm, 308);
  assert.equal(bedroom.depthCm, 239);
  assert.deepEqual(bedroom.openingChainCm, [121, 93, 72]);
  assert.equal(bedroom.openingChainCm.reduce((sum, value) => sum + value, 0) + bedroom.unassignedCm, 308);
});

test('sequential site measurements remain explicit orthogonal chains', () => {
  const livingStep = survey.measuredAreas.find((area) => area.id === 'living-step');
  const wardrobe = survey.measuredAreas.find((area) => area.id === 'hall-wardrobe');
  assert.deepEqual(livingStep.segmentsCm, [48, 46, 26, 220]);
  assert.equal(livingStep.segmentsCm.length, livingStep.directions.length);
  assert.deepEqual(wardrobe.segmentsCm, [54, 13, 40, 157, 41, 46]);
  assert.equal(wardrobe.segmentsCm.length, wardrobe.directions.length);
});

test('partial survey never claims to be a closed exact apartment footprint', () => {
  assert.equal(survey.status, 'partial_measured_survey');
  assert.ok(survey.openMeasurements.length >= 3);
});
