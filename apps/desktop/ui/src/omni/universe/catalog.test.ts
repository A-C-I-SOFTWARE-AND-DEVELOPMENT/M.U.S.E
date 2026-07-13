import assert from 'node:assert/strict';
import test from 'node:test';
import {
  DECKS,
  PLAYER_MODES,
  STATIONS,
  UNIVERSE_ROUTES,
  VESSEL_CLASSES,
  routeForPath,
} from './catalog.ts';

test('the approved universe catalog is complete and uniquely addressable', () => {
  assert.equal(DECKS.length, 5);
  assert.equal(STATIONS.length, 11);
  assert.equal(VESSEL_CLASSES.length, 9);
  assert.deepEqual(PLAYER_MODES.map((mode) => mode.id), [
    'walk',
    'pilot',
    'fleet',
    'director',
  ]);

  for (const collection of [DECKS, STATIONS, VESSEL_CLASSES, PLAYER_MODES]) {
    assert.equal(new Set(collection.map((entry) => entry.id)).size, collection.length);
  }
});

test('station interiors resolve to their functional room instead of a generic shell', () => {
  const cinema = routeForPath('/stations/cinema-array');
  assert.equal(cinema.station, 'cinema-array');
  assert.equal(cinema.room, 'cinema-array');
  assert.equal(cinema.scene, 'station-room');
});

test('every required universe destination has a room and an accessible summary', () => {
  for (const path of [
    '/atlas',
    '/stations',
    '/shipyard',
    '/fleet',
    '/agents',
    '/civilizations',
    '/fabrication',
    '/game-foundry',
    '/cinema',
    '/release',
  ]) {
    assert.ok(UNIVERSE_ROUTES.some((route) => route.path === path), path);
  }
  assert.ok(
    UNIVERSE_ROUTES.every(
      (route) => route.room && route.deck && route.station && route.accessibleSummary,
    ),
  );
});
