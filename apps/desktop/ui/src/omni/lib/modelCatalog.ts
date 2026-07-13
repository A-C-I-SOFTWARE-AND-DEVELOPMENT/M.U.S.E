// Model catalog — fetch each configured provider's models (OpenAI /models),
// fall back to its curated list, cache per-provider, and aggregate. Each model
// is tagged with its provider and the transport that would serve it.

import { getSecret } from './config';
import {
  configuredProviders,
  resolveModelTransport,
  type Provider,
  type Transport,
} from './providers';

export interface CatalogModel {
  id: string; // the id NEXUS uses (provider-qualified where helpful)
  provider: Provider;
  transport: Transport['kind'];
}

const CACHE_KEY = 'nexus.models.cache.v1';
const TTL_MS = 1000 * 60 * 60 * 12;

type Cache = Record<string, { at: number; models: string[] }>;

function readCache(): Cache {
  try { return JSON.parse(localStorage.getItem(CACHE_KEY) ?? '{}'); } catch { return {}; }
}
function writeCache(c: Cache) {
  try { localStorage.setItem(CACHE_KEY, JSON.stringify(c)); } catch { /* ignore */ }
}

/** Fetch a provider's model ids (OpenAI /models), with curated fallback + cache. */
export async function fetchModels(p: Provider, force = false): Promise<string[]> {
  const cache = readCache();
  const hit = cache[p.id];
  if (!force && hit && Date.now() - hit.at < TTL_MS) return hit.models;

  const base = p.id === 'custom' ? getSecret('CUSTOM_BASE_URL') : p.baseUrl;
  const key = getSecret(p.keyEnv);
  let models = p.curated ?? [];
  if (base && p.browserDirect && p.shape !== 'anthropic') {
    try {
      const res = await fetch(`${base.replace(/\/$/, '')}/models`, { headers: key ? { Authorization: `Bearer ${key}` } : {} });
      if (res.ok) {
        const data = await res.json();
        const ids = (data?.data ?? data?.models ?? []).map((m: any) => m?.id ?? m?.name).filter(Boolean);
        if (ids.length) models = ids;
      }
    } catch { /* keep curated */ }
  }
  cache[p.id] = { at: Date.now(), models };
  writeCache(cache);
  return models;
}

/** Aggregate models across every configured provider, tagged + transport-resolved. */
export async function allAvailableModels(force = false): Promise<CatalogModel[]> {
  const providers = configuredProviders();
  const lists = await Promise.all(providers.map((p) => fetchModels(p, force).then((ms) => ({ p, ms }))));
  const out: CatalogModel[] = [];
  for (const { p, ms } of lists) {
    for (const id of ms) {
      // qualify with provider id when the bare id would be ambiguous
      const qualified = id.includes('/') || p.id === 'openrouter' ? id : `${p.id}/${id}`;
      out.push({ id: qualified, provider: p, transport: resolveModelTransport(qualified).kind });
    }
  }
  return out;
}

export function clearModelCache() {
  try { localStorage.removeItem(CACHE_KEY); } catch { /* ignore */ }
}
