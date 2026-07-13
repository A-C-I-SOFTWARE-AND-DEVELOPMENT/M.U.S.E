import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const page = (name: string) =>
  readFileSync(new URL(`./pages/${name}.tsx`, import.meta.url), 'utf8');

test('Fabrication exposes the complete source-edit evidence lifecycle', () => {
  const source = page('FabricationPage');
  for (const label of ['Source map', 'Live preview', 'Unified diff', 'Verification', 'Checkpoint', 'Rollback', 'Stage release']) {
    assert.ok(source.includes(label), label);
  }
});

test('Game Foundry never substitutes a demo score for production evidence', () => {
  const source = page('GameFoundryPage');
  for (const label of ['GDD', 'Engine validation', 'Performance budgets', 'Package artifacts', 'Rights and ratings', 'Rollback']) {
    assert.ok(source.includes(label), label);
  }
  assert.doesNotMatch(source, /demo score/i);
});

test('Cinema Stage exposes physical stereo and deterministic QC evidence', () => {
  const source = page('CinemaStagePage');
  for (const label of ['Interaxial', 'Convergence', 'Zero parallax', 'Stereo QC', '1.90', '1.43', 'OpenEXR', 'IMAX']) {
    assert.ok(source.includes(label), label);
  }
});

test('Release Dock separates preview, promotion, durable publish, and rollback', () => {
  const source = page('ReleaseDockPage');
  for (const label of ['Private preview', 'Verification gates', 'Owner approval', 'Durable release', 'Previous version', 'Rollback']) {
    assert.ok(source.includes(label), label);
  }
});
