import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import { deriveRectangularWallProfile, expandApartmentGeometry } from '../src/geometry.js';

const apartment = JSON.parse(await readFile(new URL('../data/apartment.json', import.meta.url), 'utf8'));
const profile = apartment.wallProfiles.find((item) => item.id === 'profile-garderobe');

function vector(wall) {
  return [wall.end[0] - wall.start[0], wall.end[1] - wall.start[1]];
}

function dot(first, second) {
  return first[0] * second[0] + first[1] * second[1];
}

function cross(first, second) {
  return first[0] * second[1] - first[1] * second[0];
}

test('browser derivation creates parallel sides and a perpendicular cap', () => {
  const { walls } = deriveRectangularWallProfile(profile);
  const [baseline, cap, farSide] = walls;
  assert.ok(Math.abs(dot(vector(baseline), vector(cap))) < 1e-8);
  assert.ok(Math.abs(dot(vector(farSide), vector(cap))) < 1e-8);
  assert.ok(Math.abs(cross(vector(baseline), vector(farSide))) < 1e-8);
  assert.deepEqual(baseline.end, cap.start);
  assert.deepEqual(cap.end, farSide.start);
});

test('apartment expansion adds the derived profile exactly once', () => {
  const expanded = expandApartmentGeometry(apartment);
  const derivedWalls = expanded.walls.filter((wall) => wall.derivedFrom === profile.id);
  const derivedNiches = expanded.niches.filter((niche) => niche.derivedFrom === profile.id);
  assert.equal(derivedWalls.length, 3);
  assert.equal(derivedNiches.length, 1);
});
