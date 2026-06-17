// ============================================================================
// Runtime configuration. The one-click connect wizard writes here at runtime
// (localStorage), overriding build-time env — so NEXUS can establish the
// gateway + all connections autonomously WITHOUT a rebuild or redeploy.
//
// Every adapter reads its base URL / token / keys through these getters.
// ============================================================================

export interface RuntimeConfig {
  museBaseUrl: string;
  museToken: string; // per-device Bearer token from cockpit pairing
  supabaseUrl: string;
  supabaseAnonKey: string;
  vapidPublicKey: string;
}

const LS_KEY = 'nexus.config.v1';

function envDefaults(): RuntimeConfig {
  return {
    museBaseUrl: import.meta.env.VITE_MUSE_BASE_URL ?? '',
    museToken: '',
    supabaseUrl: import.meta.env.VITE_SUPABASE_URL ?? '',
    supabaseAnonKey: import.meta.env.VITE_SUPABASE_ANON_KEY ?? '',
    vapidPublicKey: import.meta.env.VITE_VAPID_PUBLIC_KEY ?? '',
  };
}

let cache: RuntimeConfig | null = null;

function read(): RuntimeConfig {
  if (cache) return cache;
  const env = envDefaults();
  if (typeof localStorage === 'undefined') return (cache = env);
  try {
    const stored = JSON.parse(localStorage.getItem(LS_KEY) ?? '{}') as Partial<RuntimeConfig>;
    // Stored values win over env, but only when non-empty.
    cache = {
      museBaseUrl: stored.museBaseUrl || env.museBaseUrl,
      museToken: stored.museToken || env.museToken,
      supabaseUrl: stored.supabaseUrl || env.supabaseUrl,
      supabaseAnonKey: stored.supabaseAnonKey || env.supabaseAnonKey,
      vapidPublicKey: stored.vapidPublicKey || env.vapidPublicKey,
    };
  } catch {
    cache = env;
  }
  return cache;
}

export function getConfig(): RuntimeConfig {
  return { ...read() };
}

export function setConfig(patch: Partial<RuntimeConfig>): void {
  const next = { ...read(), ...patch };
  cache = next;
  try {
    localStorage.setItem(LS_KEY, JSON.stringify(next));
  } catch {
    /* storage may be unavailable */
  }
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('nexus:config'));
  }
}

export function resetConfig(): void {
  cache = null;
  try {
    localStorage.removeItem(LS_KEY);
  } catch {
    /* ignore */
  }
  if (typeof window !== 'undefined') window.dispatchEvent(new CustomEvent('nexus:config'));
}

// ---- Convenience getters used by every adapter ----
export const museBase = (): string => read().museBaseUrl.replace(/\/$/, '');
export const museToken = (): string => read().museToken;
export const supabaseUrlCfg = (): string => read().supabaseUrl.replace(/\/$/, '');
export const supabaseAnonCfg = (): string => read().supabaseAnonKey;
export const vapidKey = (): string => read().vapidPublicKey;

/** Bearer auth headers for the cockpit gateway (empty until paired). */
export function authHeaders(): Record<string, string> {
  const t = museToken();
  return t ? { Authorization: `Bearer ${t}` } : {};
}

export function isConfigured(): boolean {
  return !!museBase();
}

// ---- Third-party secrets bag (keyed by canonical ENV var name) -------------
// Stored separately from RuntimeConfig. The app applies "local" creds directly;
// "gateway" creds are collected here and exported as a ready-to-apply .env
// snippet for the gateway host (MUSE keeps provider/messaging keys in
// ~/.hermes/.env — there is no remote secrets endpoint, by design).

const SECRETS_KEY = 'nexus.secrets.v1';
let secretsCache: Record<string, string> | null = null;

function readSecrets(): Record<string, string> {
  if (secretsCache) return secretsCache;
  if (typeof localStorage === 'undefined') return (secretsCache = {});
  try {
    secretsCache = JSON.parse(localStorage.getItem(SECRETS_KEY) ?? '{}');
  } catch {
    secretsCache = {};
  }
  return secretsCache!;
}

export function getSecret(env: string): string {
  return readSecrets()[env] ?? '';
}

export function getSecrets(): Record<string, string> {
  return { ...readSecrets() };
}

export function setSecret(env: string, value: string): void {
  const next = { ...readSecrets() };
  if (value) next[env] = value;
  else delete next[env];
  secretsCache = next;
  try {
    localStorage.setItem(SECRETS_KEY, JSON.stringify(next));
  } catch {
    /* ignore */
  }
  if (typeof window !== 'undefined') window.dispatchEvent(new CustomEvent('nexus:config'));
}

/** Build a ready-to-apply ~/.hermes/.env snippet from the stored gateway secrets. */
export function envSnippet(envKeys: string[]): string {
  const s = readSecrets();
  const lines = envKeys.filter((k) => s[k]).map((k) => `${k}=${s[k]}`);
  return lines.join('\n');
}
