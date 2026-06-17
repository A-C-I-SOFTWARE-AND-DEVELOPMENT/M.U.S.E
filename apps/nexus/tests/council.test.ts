import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { dispatchCouncil } from '../src/lib/council';
import { resetConfig, setConfig } from '../src/lib/config';

function mockFetch(status: number, body: unknown) {
  return vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  });
}

const GW = 'http://127.0.0.1:8765';

describe('council dispatch client', () => {
  beforeEach(() => resetConfig());
  afterEach(() => vi.restoreAllMocks());

  it('no gateway → honest error', async () => {
    const r = await dispatchCouncil('do a thing');
    expect(r.ok).toBe(false);
    expect(r.error).toMatch(/No gateway/);
  });

  it('maps the session payload (engaged_count → engagedCount, owner_gated)', async () => {
    setConfig({ museBaseUrl: GW });
    vi.stubGlobal(
      'fetch',
      mockFetch(200, {
        request: 'arch',
        council: [{ id: 'council-director', kind: 'council' }],
        specialists: [{ id: 'principal-systems-architect', kind: 'specialist', owner_gated: true }],
        engaged_count: 2,
        owner_gated: true,
      }),
    );
    const r = await dispatchCouncil('arch');
    expect(r.ok).toBe(true);
    expect(r.engagedCount).toBe(2);
    expect(r.ownerGated).toBe(true);
    expect(r.specialists[0].id).toBe('principal-systems-architect');
  });

  it('encodes the request in the query string', async () => {
    setConfig({ museBaseUrl: GW });
    const f = mockFetch(200, { council: [], specialists: [], engaged_count: 0, owner_gated: false });
    vi.stubGlobal('fetch', f);
    await dispatchCouncil('a & b');
    expect(f.mock.calls[0][0] as string).toContain('q=a%20%26%20b');
  });
});
