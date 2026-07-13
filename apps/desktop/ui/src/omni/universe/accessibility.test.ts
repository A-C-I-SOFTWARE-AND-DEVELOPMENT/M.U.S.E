import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const css = readFileSync(new URL('../styles/tokens.css', import.meta.url), 'utf8');
const scene = readFileSync(new URL('./scene/UniverseScene.tsx', import.meta.url), 'utf8');
const neuralHud = readFileSync(new URL('./components/NeuralCoreHud.tsx', import.meta.url), 'utf8');
const vessel = readFileSync(new URL('./scene/AgentVessel.tsx', import.meta.url), 'utf8');
const vesselHud = readFileSync(new URL('./components/VesselHud.tsx', import.meta.url), 'utf8');

test('global comfort and contrast contracts are present', () => {
  assert.match(css, /prefers-reduced-motion/);
  assert.match(css, /prefers-contrast/);
  assert.match(css, /forced-colors/);
  assert.match(css, /:focus-visible/);
  assert.match(css, /universe-2d-fallback/);
});

test('3D interaction always has a labeled 2D control equivalent', () => {
  assert.match(scene, /aria-hidden="true"/);
  assert.doesNotMatch(vessel, /onClick=/);
  assert.match(neuralHud, /role="tree"/);
  assert.match(neuralHud, /<button/);
  assert.match(vesselHud, /aria-label=/);
  assert.match(vesselHud, /<button/);
});
