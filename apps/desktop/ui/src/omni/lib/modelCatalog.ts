// Model catalog — fetch each configured provider's models (OpenAI /models),
// fall back to its curated list, cache per-provider, and aggregate. Each model
// is tagged with its provider and the transport that would serve it.

import { getSecret } from './config';
import { configuredProviders, resolveModelTransport, type Provider, type Transport } from './providers';

export interface CatalogModel {
  id: string; // the id NEXUS uses (provider-qualified where helpful)
  provider: Provider;
  transport: Transport['kind'];
}

const CACHE_KEY = 'nexus.models.cache.v2'; // v2 adds live models.dev data
const TTL_MS = 1000 * 60 * 60 * 12;
const MODELS_DEV_URL = 'https://models.dev/api.json';
const MODELS_DEV_TTL_MS = 1000 * 60 * 60;
const MODELS_DEV_FORCE_DEDUP_MS = 30_000;

type Cache = Record<string, { at: number; models: string[] }>;
type ModelsDevRegistry = Record<string, { models?: Record<string, { id?: string; tool_call?: boolean; release_date?: string; last_updated?: string }> }>;

let modelsDevRegistry: ModelsDevRegistry | null = null;
let modelsDevFetchedAt = 0;
let modelsDevInFlight: Promise<ModelsDevRegistry | null> | null = null;

function readCache(): Cache {
  try {
    return JSON.parse(localStorage.getItem(CACHE_KEY) ?? '{}');
  } catch {
    return {};
  }
}
function writeCache(c: Cache) {
  try {
    localStorage.setItem(CACHE_KEY, JSON.stringify(c));
  } catch {
    /* ignore */
  }
}

async function fetchModelsDev(force = false): Promise<ModelsDevRegistry | null> {
  const maxAge = force ? MODELS_DEV_FORCE_DEDUP_MS : MODELS_DEV_TTL_MS;
  if (modelsDevRegistry && Date.now() - modelsDevFetchedAt < maxAge) {
    return modelsDevRegistry;
  }
  if (modelsDevInFlight) return modelsDevInFlight;

  modelsDevInFlight = fetch(MODELS_DEV_URL)
    .then(async (res) => {
      if (!res.ok) return null;
      const data = await res.json();
      if (!data || typeof data !== 'object' || Array.isArray(data)) return null;
      modelsDevRegistry = data as ModelsDevRegistry;
      modelsDevFetchedAt = Date.now();
      return modelsDevRegistry;
    })
    .catch(() => null)
    .finally(() => {
      modelsDevInFlight = null;
    });
  return modelsDevInFlight;
}

function modelsDevIds(registry: ModelsDevRegistry | null, p: Provider): string[] {
  if (!registry || !p.modelsDevId) return [];
  const models = registry[p.modelsDevId]?.models;
  if (!models) return [];

  return Object.entries(models)
    .filter(([, metadata]) => metadata?.tool_call === true)
    .sort(([, a], [, b]) => {
      const aDate = a.last_updated || a.release_date || '';
      const bDate = b.last_updated || b.release_date || '';
      return bDate.localeCompare(aDate);
    })
    .map(([key, metadata]) => metadata.id || key)
    .map((id) => (p.id === 'ollama-cloud' ? id.replace(/(?::cloud|-cloud)$/, '') : id));
}

function mergeModels(...lists: string[][]): string[] {
  const seen = new Set<string>();
  const merged: string[] = [];
  for (const list of lists) {
    for (const id of list) {
      const key = id.toLowerCase();
      if (!id || seen.has(key)) continue;
      seen.add(key);
      merged.push(id);
    }
  }
  return merged;
}

/** Fetch live + models.dev model ids, with curated offline fallback + cache. */
export async function fetchModels(p: Provider, force = false): Promise<string[]> {
  const cache = readCache();
  const hit = cache[p.id];
  if (!force && hit && Date.now() - hit.at < TTL_MS) return hit.models;

  const base = p.id === 'custom' ? getSecret('CUSTOM_BASE_URL') : p.baseUrl;
  const key = getSecret(p.keyEnv);
  let liveModels: string[] = [];
  if (base && p.browserDirect && p.shape !== 'anthropic') {
    try {
      const res = await fetch(`${base.replace(/\/$/, '')}/models`, { headers: key ? { Authorization: `Bearer ${key}` } : {} });
      if (res.ok) {
        const data = await res.json();
        const ids = (data?.data ?? data?.models ?? []).map((m: any) => m?.id ?? m?.name).filter(Boolean);
        if (ids.length) liveModels = ids;
      }
    } catch {
      /* keep curated */
    }
  }
  const registry = await fetchModelsDev(force);
  const models = mergeModels(liveModels, modelsDevIds(registry, p), p.curated ?? []);
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
      // Preserve OpenRouter's vendor/model slugs. Every direct provider gets
      // its provider prefix even when its native model ID already contains
      // slashes (for example gmi/zai-org/GLM-5.2-FP8).
      const qualified = p.id === 'openrouter' ? id : `${p.id}/${id}`;
      out.push({ id: qualified, provider: p, transport: resolveModelTransport(qualified).kind });
    }
  }
  return out;
}

export function clearModelCache() {
  try {
    localStorage.removeItem(CACHE_KEY);
  } catch {
    /* ignore */
  }
  modelsDevRegistry = null;
  modelsDevFetchedAt = 0;
  modelsDevInFlight = null;
}
