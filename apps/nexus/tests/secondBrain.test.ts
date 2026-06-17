import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { fetchSecondBrainStatus, retrieveSecondBrain } from '../src/lib/secondBrain';
import { resetConfig, setConfig } from '../src/lib/config';

function mockFetch(status: number, body: unknown) {
  return vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  });
}

const GW = 'http://127.0.0.1:8765';

describe('secondBrain client', () => {
  beforeEach(() => resetConfig());
  afterEach(() => vi.restoreAllMocks());

  it('status: no gateway → not connected', async () => {
    const s = await fetchSecondBrainStatus();
    expect(s.enabled).toBe(false);
    expect(s.error).toMatch(/No gateway/);
  });

  it('status: parses enabled/available/backend', async () => {
    setConfig({ museBaseUrl: GW });
    vi.stubGlobal('fetch', mockFetch(200, { enabled: true, available: true, settings: { backend: 'memory' } }));
    const s = await fetchSecondBrainStatus();
    expect(s).toEqual({ enabled: true, available: true, backend: 'memory', error: undefined });
  });

  it('retrieve: no gateway → honest error', async () => {
    const r = await retrieveSecondBrain('q');
    expect(r.ok).toBe(false);
    expect(r.error).toMatch(/No gateway/);
  });

  it('retrieve: maps the fused payload', async () => {
    setConfig({ museBaseUrl: GW });
    vi.stubGlobal('fetch', mockFetch(200, { enabled: true, available: true, backend_ready: true, blocks: 2, text: 'FUSED' }));
    const r = await retrieveSecondBrain('who', 5);
    expect(r).toEqual({ ok: true, enabled: true, available: true, backendReady: true, blocks: 2, text: 'FUSED' });
  });

  it('retrieve: 401 → pairing hint', async () => {
    setConfig({ museBaseUrl: GW });
    vi.stubGlobal('fetch', mockFetch(401, {}));
    const r = await retrieveSecondBrain('q');
    expect(r.ok).toBe(false);
    expect(r.error).toMatch(/pair/i);
  });

  it('retrieve: encodes q and top_k in the URL', async () => {
    setConfig({ museBaseUrl: GW });
    const f = mockFetch(200, { enabled: true, available: true, backend_ready: true, blocks: 1, text: 'x' });
    vi.stubGlobal('fetch', f);
    await retrieveSecondBrain('hello world', 7);
    const url = f.mock.calls[0][0] as string;
    expect(url).toContain('/v1/cockpit/second-brain/retrieve?');
    expect(url).toContain('q=hello+world');
    expect(url).toContain('top_k=7');
  });
});
