import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { fetchForgeLeaderboard } from '../src/lib/forgeArena';
import { fetchFederationStatus } from '../src/lib/federation';
import { resetConfig, setConfig } from '../src/lib/config';

function mockFetch(status: number, body: unknown) {
  return vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  });
}

const GW = 'http://127.0.0.1:8765';

describe('forge championship client', () => {
  beforeEach(() => resetConfig());
  afterEach(() => vi.restoreAllMocks());

  it('no gateway → honest error', async () => {
    const r = await fetchForgeLeaderboard();
    expect(r.ok).toBe(false);
    expect(r.error).toMatch(/No gateway/);
  });

  it('maps the leaderboard payload (qd_score → qdScore)', async () => {
    setConfig({ museBaseUrl: GW });
    vi.stubGlobal(
      'fetch',
      mockFetch(200, { standings: [{ candidate_id: 'a' }], candidates: 1, coverage: 0.5, qd_score: 1.25 }),
    );
    const r = await fetchForgeLeaderboard();
    expect(r).toEqual({ ok: true, standings: [{ candidate_id: 'a' }], candidates: 1, coverage: 0.5, qdScore: 1.25 });
  });
});

describe('federation client', () => {
  beforeEach(() => resetConfig());
  afterEach(() => vi.restoreAllMocks());

  it('no gateway → honest error', async () => {
    const r = await fetchFederationStatus();
    expect(r.ok).toBe(false);
    expect(r.error).toMatch(/No gateway/);
  });

  it('maps the status payload (public identity + peers)', async () => {
    setConfig({ museBaseUrl: GW });
    const identity = {
      node_id: 'node_x',
      display_name: 'n',
      created_at: 't',
      algo: 'ed25519',
      public_key_hex: 'ab',
    };
    vi.stubGlobal('fetch', mockFetch(200, { identity, peers: [{ node_id: 'p1' }], peer_count: 1 }));
    const r = await fetchFederationStatus();
    expect(r).toEqual({ ok: true, identity, peers: [{ node_id: 'p1' }], peerCount: 1 });
  });
});
