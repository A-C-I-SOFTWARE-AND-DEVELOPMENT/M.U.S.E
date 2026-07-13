import assert from 'node:assert/strict';
import test from 'node:test';
import { buildVisibleGraph, levelForDistance, mergeGraphNodes, projectUniverseGraph } from './semanticZoom.ts';
import type { GraphNode } from './semanticZoom.ts';

const node = (id: string, position: [number, number, number], version = 1): GraphNode => ({
  id,
  label: id,
  type: 'signal',
  position,
  status: 'observed',
  observedAt: '2026-07-12T00:00:00Z',
  source: 'test',
  confidence: 1,
  version,
  evidence: [],
});

test('semantic zoom selects exactly one level at each distance', () => {
  assert.equal(levelForDistance(1800), 'orbital');
  assert.equal(levelForDistance(600), 'deck');
  assert.equal(levelForDistance(180), 'mission');
  assert.equal(levelForDistance(45), 'artifact');
  assert.equal(levelForDistance(8), 'signal');
});

test('visual proximity never invents a relationship', () => {
  const graph = buildVisibleGraph(
    [node('a', [0, 0, 0]), node('b', [0.01, 0, 0])],
    [],
  );
  assert.deepEqual(graph.edges, []);
});

test('stream merges retain the newest stable node version', () => {
  const merged = mergeGraphNodes([node('a', [0, 0, 0], 2)], [node('a', [1, 0, 0], 1)]);
  assert.deepEqual(merged[0]?.position, [0, 0, 0]);
});

test('universe projection uses only explicitly reported edges', () => {
  const projected = projectUniverseGraph({
    realms: [
      { id: 'a', entity_type: 'realm', realm_id: 'rlm_1', version: 1, updated_at: '2026-07-12T00:00:00Z', simulation: false },
      { id: 'b', entity_type: 'realm', realm_id: 'rlm_1', version: 1, updated_at: '2026-07-12T00:00:00Z', simulation: false },
    ],
  });
  assert.equal(projected.nodes.length, 2);
  assert.deepEqual(projected.edges, []);
});
