// ============================================================================
// Runtime configuration. The connect wizard / credentials manager write here at
// runtime so NEXUS configures itself WITHOUT a rebuild.
//
// Storage is split by sensitivity:
//   • NON-sensitive (gateway URL, Supabase project URL) → plaintext localStorage
//     (kept sync so first-paint gating like isConfigured() is correct).
//   • SENSITIVE (device token, Supabase anon key, VAPID key, and every
//     third-party API key/token) → ENCRYPTED AT REST via securestore.ts
//     (AES-GCM with a non-extractable IndexedDB key). Never stored clear-text.
// ============================================================================

import { encryptJson, decryptJson, secureAvailable } from './securestore';

export interface RuntimeConfig {
  museBaseUrl: string;
  museToken: string; // per-device Bearer token from cockpit pairing
  supabaseUrl: string;
  supabaseAnonKey: string;
  vapidPublicKey: string;
  repoSlug: string; // MUSE repo mirror source, e.g. "owner/repo" (non-sensitive)
  repoBranch: string; // branch to mirror, default "main"
}

const PLAIN_KEY = 'nexus.cfg.v2'; // non-sensitive only
const SECURE_KEY = 'nexus.secure.v1'; // ciphertext blob
const LEGACY_CFG = 'nexus.config.v1'; // pre-encryption combined plaintext
const LEGACY_SECRETS = 'nexus.secrets.v1'; // pre-encryption plaintext secrets

// Reserved secure-bag keys for the sensitive RuntimeConfig fields (won't collide
// with the UPPERCASE third-party ENV names that share the bag).
const K_TOKEN = 'museToken';
const K_ANON = 'supabaseAnonKey';
const K_VAPID = 'vapidPublicKey';

interface PlainCfg {
  museBaseUrl: string;
  supabaseUrl: string;
  repoSlug: string;
  repoBranch: string;
}

let plainCache: PlainCfg | null = null;
let secureCache: Record<string, string> = {};
let hydrated = false;

function emit() {
  if (typeof window !== 'undefined') window.dispatchEvent(new CustomEvent('nexus:config'));
}

function readPlain(): PlainCfg {
  if (plainCache) return plainCache;
  const def: PlainCfg = {
    museBaseUrl: import.meta.env.VITE_MUSE_BASE_URL ?? '',
    supabaseUrl: import.meta.env.VITE_SUPABASE_URL ?? '',
    repoSlug: import.meta.env.VITE_REPO_SLUG ?? '',
    repoBranch: import.meta.env.VITE_REPO_BRANCH ?? '',
  };
  if (typeof localStorage === 'undefined') return (plainCache = def);
  try {
    const s = JSON.parse(localStorage.getItem(PLAIN_KEY) ?? '{}') as Partial<PlainCfg>;
    plainCache = {
      museBaseUrl: s.museBaseUrl || def.museBaseUrl,
      supabaseUrl: s.supabaseUrl || def.supabaseUrl,
      repoSlug: s.repoSlug || def.repoSlug,
      repoBranch: s.repoBranch || def.repoBranch,
    };
  } catch {
    plainCache = def;
  }
  return plainCache;
}

function persistPlain() {
  try {
    localStorage.setItem(PLAIN_KEY, JSON.stringify(readPlain()));
  } catch {
    /* ignore */
  }
}

async function persistSecure() {
  if (typeof localStorage === 'undefined') return;
  // Only persist when WebCrypto is available; otherwise keep secrets session-only
  // (in-memory) rather than ever writing clear text.
  if (!secureAvailable()) return;
  try {
    const blob = await encryptJson(secureCache);
    localStorage.setItem(SECURE_KEY, blob);
  } catch {
    /* ignore */
  }
}

/** Async hydrate of the encrypted secrets + one-time migration of legacy plaintext. */
async function hydrate(): Promise<void> {
  if (hydrated || typeof localStorage === 'undefined') return;
  hydrated = true;
  let dirtyPlain = false;
  let dirtySecure = false;

  // Migrate legacy combined plaintext config.
  const legacyCfg = localStorage.getItem(LEGACY_CFG);
  if (legacyCfg) {
    try {
      const c = JSON.parse(legacyCfg) as Partial<RuntimeConfig>;
      const p = readPlain();
      if (c.museBaseUrl) { p.museBaseUrl = c.museBaseUrl; dirtyPlain = true; }
      if (c.supabaseUrl) { p.supabaseUrl = c.supabaseUrl; dirtyPlain = true; }
      if (c.museToken) { secureCache[K_TOKEN] = c.museToken; dirtySecure = true; }
      if (c.supabaseAnonKey) { secureCache[K_ANON] = c.supabaseAnonKey; dirtySecure = true; }
      if (c.vapidPublicKey) { secureCache[K_VAPID] = c.vapidPublicKey; dirtySecure = true; }
    } catch {
      /* ignore */
    }
    localStorage.removeItem(LEGACY_CFG);
  }

  // Migrate legacy plaintext secrets bag.
  const legacySecrets = localStorage.getItem(LEGACY_SECRETS);
  if (legacySecrets) {
    try {
      Object.assign(secureCache, JSON.parse(legacySecrets));
      dirtySecure = true;
    } catch {
      /* ignore */
    }
    localStorage.removeItem(LEGACY_SECRETS);
  }

  // Load the encrypted blob.
  const blob = localStorage.getItem(SECURE_KEY);
  if (blob) {
    const obj = await decryptJson<Record<string, string>>(blob);
    if (obj) secureCache = { ...obj, ...secureCache };
  }

  if (dirtyPlain) persistPlain();
  if (dirtySecure || legacyCfg || legacySecrets) await persistSecure();
  emit();
}

// Kick off hydration immediately (non-blocking).
if (typeof window !== 'undefined') void hydrate();

const sec = (k: string, envFallback = ''): string => secureCache[k] || envFallback;

export function getConfig(): RuntimeConfig {
  const p = readPlain();
  return {
    museBaseUrl: p.museBaseUrl,
    supabaseUrl: p.supabaseUrl,
    repoSlug: p.repoSlug,
    repoBranch: p.repoBranch,
    museToken: sec(K_TOKEN),
    supabaseAnonKey: sec(K_ANON, import.meta.env.VITE_SUPABASE_ANON_KEY ?? ''),
    vapidPublicKey: sec(K_VAPID, import.meta.env.VITE_VAPID_PUBLIC_KEY ?? ''),
  };
}

export function setConfig(patch: Partial<RuntimeConfig>): void {
  const p = readPlain();
  if (patch.museBaseUrl !== undefined) { p.museBaseUrl = patch.museBaseUrl; persistPlain(); }
  if (patch.supabaseUrl !== undefined) { p.supabaseUrl = patch.supabaseUrl; persistPlain(); }
  if (patch.repoSlug !== undefined) { p.repoSlug = patch.repoSlug; persistPlain(); }
  if (patch.repoBranch !== undefined) { p.repoBranch = patch.repoBranch; persistPlain(); }
  let touchedSecure = false;
  if (patch.museToken !== undefined) { secureCache[K_TOKEN] = patch.museToken; touchedSecure = true; }
  if (patch.supabaseAnonKey !== undefined) { secureCache[K_ANON] = patch.supabaseAnonKey; touchedSecure = true; }
  if (patch.vapidPublicKey !== undefined) { secureCache[K_VAPID] = patch.vapidPublicKey; touchedSecure = true; }
  if (touchedSecure) void persistSecure();
  emit();
}

export function resetConfig(): void {
  plainCache = { museBaseUrl: '', supabaseUrl: '', repoSlug: '', repoBranch: '' };
  secureCache = {};
  try {
    localStorage.removeItem(PLAIN_KEY);
    localStorage.removeItem(SECURE_KEY);
  } catch {
    /* ignore */
  }
  emit();
}

// ---- Convenience getters used by every adapter ----
export const museBase = (): string => readPlain().museBaseUrl.replace(/\/$/, '');
export const museToken = (): string => sec(K_TOKEN);
export const supabaseUrlCfg = (): string => readPlain().supabaseUrl.replace(/\/$/, '');
export const supabaseAnonCfg = (): string => sec(K_ANON, import.meta.env.VITE_SUPABASE_ANON_KEY ?? '');
export const vapidKey = (): string => sec(K_VAPID, import.meta.env.VITE_VAPID_PUBLIC_KEY ?? '');

/** Bearer auth headers for the cockpit gateway (empty until paired). */
export function authHeaders(): Record<string, string> {
  const t = museToken();
  return t ? { Authorization: `Bearer ${t}` } : {};
}

export function isConfigured(): boolean {
  return !!museBase();
}

// ---- Third-party secrets bag (keyed by canonical ENV var name) -------------
// Shares the ENCRYPTED secureCache. "local" creds apply via setConfig; "gateway"
// creds live here and export as a ~/.hermes/.env snippet (MUSE keeps
// provider/messaging keys server-side — no remote secrets endpoint, by design).

export function getSecret(env: string): string {
  return secureCache[env] ?? '';
}

export function getSecrets(): Record<string, string> {
  return { ...secureCache };
}

export function setSecret(env: string, value: string): void {
  if (value) secureCache[env] = value;
  else delete secureCache[env];
  void persistSecure();
  emit();
}

/** Build a ready-to-apply ~/.hermes/.env snippet from the stored gateway secrets. */
export function envSnippet(envKeys: string[]): string {
  return envKeys.filter((k) => secureCache[k]).map((k) => `${k}=${secureCache[k]}`).join('\n');
}
