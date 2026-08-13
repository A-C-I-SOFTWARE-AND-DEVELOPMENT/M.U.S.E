import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { resetConfig, setSecret } from '../src/lib/config';
import { allAvailableModels, clearModelCache, fetchModels } from '../src/lib/modelCatalog';
import { getProvider } from '../src/lib/providers';

beforeEach(() => {
  resetConfig();
  clearModelCache();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('live provider model catalog', () => {
  it('keeps Kimi K3 in the Ollama Cloud offline fallback', () => {
    const ollamaCloud = getProvider('ollama-cloud');
    expect(ollamaCloud?.curated).toContain('kimi-k3');
    expect(ollamaCloud?.browserDirect).toBe(false);
  });

  it('loads Ollama Cloud from models.dev without a browser-CORS request', async () => {
    setSecret('OLLAMA_API_KEY', 'test-key');
    const fetchMock = vi.fn(async (input: string | URL | Request) => {
      const url = String(input);
      if (url === 'https://models.dev/api.json') {
        return { ok: true, json: async () => ({ 'ollama-cloud': { models: { 'kimi-k3:cloud': { id: 'kimi-k3:cloud', tool_call: true, last_updated: '2026-07-27' }, 'embedding-only': { id: 'embedding-only', tool_call: false, last_updated: '2026-07-30' } } } }) };
      }
      throw new Error(`unexpected browser request: ${url}`);
    });
    vi.stubGlobal('fetch', fetchMock);

    const models = await fetchModels(getProvider('ollama-cloud')!, true);

    expect(models[0]).toBe('kimi-k3');
    expect(models).toContain('glm-5.2');
    expect(models).toContain('kimi-k3');
    expect(models).not.toContain('kimi-k3:cloud');
    expect(models).not.toContain('embedding-only');
    expect(fetchMock).toHaveBeenCalledWith('https://models.dev/api.json');
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('keeps nested native model IDs attached to their direct provider', async () => {
    setSecret('GMI_API_KEY', 'test-key');
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: string | URL | Request) => ({
        ok: true,
        json: async () =>
          String(input) === 'https://models.dev/api.json'
            ? {
                gmicloud: {
                  models: {
                    'zai-org/GLM-5.2-FP8': {
                      id: 'zai-org/GLM-5.2-FP8',
                      tool_call: true,
                    },
                  },
                },
              }
            : { data: [] },
      })),
    );

    const models = await allAvailableModels(true);
    const gmi = models.find((model) => model.id === 'gmi/zai-org/GLM-5.2-FP8');

    expect(gmi?.provider.id).toBe('gmi');
    expect(gmi?.transport).toBe('direct');
  });
});
