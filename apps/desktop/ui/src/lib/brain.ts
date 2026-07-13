/**
 * Brain (gateway process) bridge — the typed wrapper over the native shell's
 * brain commands (src-tauri/src/brain.rs): gateway_status / gateway_start /
 * gateway_stop / autostart_get / autostart_set.
 *
 * The Tauri shell is configured with `withGlobalTauri: true`, so the commands
 * are reached through `window.__TAURI__.core.invoke` — no npm dependency. In a
 * plain browser (the PWA build) the global is absent and every helper resolves
 * to null, so views treat "no native shell" as a first-class state rather than
 * an error.
 */

export type BrainStatus = {
  /** GET /v1/health answered OK right now. */
  reachable: boolean;
  /** The native shell spawned (and still tracks) the gateway process. */
  managed: boolean;
  /** Detected `muse` binary path, or null when none was found. */
  binary: string | null;
  /** Persisted autostart preference. */
  autostart: boolean;
  /** The gateway base URL the shell probes. */
  base: string;
};

type InvokeFn = (cmd: string, args?: Record<string, unknown>) => Promise<unknown>;

type TauriGlobal = {
  __TAURI__?: { core?: { invoke?: InvokeFn } };
};

function invokeFn(): InvokeFn | null {
  const g = window as unknown as TauriGlobal;
  return g.__TAURI__?.core?.invoke ?? null;
}

/** True iff the native shell (and therefore the brain commands) is present. */
export function brainAvailable(): boolean {
  return invokeFn() != null;
}

/** Current brain status, or null outside the native shell. */
export async function brainStatus(): Promise<BrainStatus | null> {
  const inv = invokeFn();
  if (!inv) return null;
  return (await inv("gateway_status")) as BrainStatus;
}

/**
 * Start the brain (spawns `muse cockpit serve` if it isn't already running).
 * Rejects with a string message when no `muse` binary is installed.
 */
export async function brainStart(): Promise<BrainStatus | null> {
  const inv = invokeFn();
  if (!inv) return null;
  return (await inv("gateway_start")) as BrainStatus;
}

/** Stop the managed brain child (an externally-started gateway is untouched). */
export async function brainStop(): Promise<BrainStatus | null> {
  const inv = invokeFn();
  if (!inv) return null;
  return (await inv("gateway_stop")) as BrainStatus;
}

/** Read the persisted autostart preference, or null outside the shell. */
export async function autostartGet(): Promise<boolean | null> {
  const inv = invokeFn();
  if (!inv) return null;
  return (await inv("autostart_get")) as boolean;
}

/** Persist the autostart preference. */
export async function autostartSet(enabled: boolean): Promise<boolean | null> {
  const inv = invokeFn();
  if (!inv) return null;
  return (await inv("autostart_set", { enabled })) as boolean;
}
