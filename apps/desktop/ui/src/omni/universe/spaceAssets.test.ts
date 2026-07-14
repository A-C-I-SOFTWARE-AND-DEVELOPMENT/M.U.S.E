import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

import { SPACE_PLATES, listSpacePlates } from './spaceAssets.ts';

const PUBLIC_DIR = join(dirname(fileURLToPath(import.meta.url)), '..', '..', '..', 'public');

test('every declared space plate ships in public/ with its attribution', () => {
  const plates = listSpacePlates();
  assert.ok(plates.length >= 4, 'expected the four core plates');
  for (const plate of plates) {
    assert.match(plate.path, /^\.\/space\//, `${plate.path} must be root-relative under ./space/`);
    assert.ok(plate.credit.length > 10, `${plate.path} needs a real credit line`);
    assert.equal(plate.width, plate.height * 2, `${plate.path} must be equirectangular 2:1`);
    const onDisk = join(PUBLIC_DIR, plate.path.replace('./', ''));
    assert.ok(existsSync(onDisk), `missing shipped plate: ${onDisk}`);
  }
  const attribution = readFileSync(join(PUBLIC_DIR, 'space', 'ATTRIBUTION.md'), 'utf8');
  assert.match(attribution, /NASA/, 'attribution must name NASA');
  for (const plate of plates) {
    const basename = plate.path.split('/').pop() as string;
    assert.match(attribution, new RegExp(basename), `attribution must cover ${basename}`);
  }
});

test('night and day plates are distinct NASA sources', () => {
  assert.notEqual(SPACE_PLATES.earthDay.path, SPACE_PLATES.earthNight.path);
  assert.match(SPACE_PLATES.earthDay.credit, /Blue Marble/);
  assert.match(SPACE_PLATES.earthNight.credit, /Black Marble/);
});
