import assert from 'node:assert/strict';
import test from 'node:test';
import { selectFidelity } from './fidelity.ts';

test('reduced capability keeps the station identity while lowering render cost', () => {
  assert.equal(
    selectFidelity({ gpuTier: 0, memoryGb: 4, reducedMotion: false }, 'auto').tier,
    'accessible-2d',
  );
  const balanced = selectFidelity(
    { gpuTier: 1, memoryGb: 8, reducedMotion: false },
    'auto',
  );
  assert.equal(balanced.tier, 'balanced');
  assert.equal(balanced.stationSilhouette, true);
  assert.equal(balanced.volumetricLayers, 1);
});

test('reduced motion disables every continuous scene motion budget', () => {
  const settings = selectFidelity(
    { gpuTier: 3, memoryGb: 16, reducedMotion: true },
    'ultra',
  );
  assert.equal(settings.motion, false);
  assert.equal(settings.comets, 0);
  assert.equal(settings.cameraDrift, 0);
  assert.equal(settings.dustCount, 0);
});

test('accessible 2D keeps controls while declining the WebGL mount', () => {
  const settings = selectFidelity(
    { gpuTier: 3, memoryGb: 16, reducedMotion: false },
    'accessible-2d',
  );
  assert.equal(settings.mount3d, false);
  assert.equal(settings.stationSilhouette, true);
});
