import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { UNIVERSE_ROUTES } from './catalog.ts';

const app = readFileSync(new URL('../App.tsx', import.meta.url), 'utf8');
const sideNav = readFileSync(new URL('../components/shell/SideNav.tsx', import.meta.url), 'utf8');
const studio = readFileSync(new URL('../pages/StudioPage.tsx', import.meta.url), 'utf8');

test('every universe route is registered and every primary route is navigable', () => {
  for (const route of UNIVERSE_ROUTES) {
    assert.ok(app.includes(`path="${route.path}"`), `route ${route.path}`);
    if (route.primary) {
      assert.ok(sideNav.includes(`to: '${route.path}'`), `navigation ${route.path}`);
    }
  }
});

test('the Studio production command deck never renders a null surface', () => {
  assert.doesNotMatch(studio, /return\s+null/);
});
