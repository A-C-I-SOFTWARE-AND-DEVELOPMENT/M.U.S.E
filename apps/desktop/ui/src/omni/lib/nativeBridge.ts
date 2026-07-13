// ============================================================================
// Native shell bridge — the PWA side of the unified-app NexusBridge.
//
// When NEXUS runs inside the native Android shell (WebViewHostActivity), the
// host injects a `window.NexusBridge` object that grants the few capabilities a
// browser cannot have: the cockpit bearer token, the always-on voice loop, the
// avatar overlay, and the emergency stop. In a plain browser the global is
// absent and every helper here degrades to a safe no-op / null, so callers can
// feature-detect with `isNativeShell()` and fall back to the existing web
// behavior (the same "requires gateway" honesty the rest of the app uses).
//
// Contract + threading model: docs/mobile/NEXUS_UNIFIED_APP_PLAN.md.
// Native impl: apps/android/.../ui/web/NexusBridge.kt (bridgeVersion === 1).
// ============================================================================

/** The shape the native host injects. All methods are synchronous (binder). */
interface NexusNativeBridge {
  shellInfo(): string;
  getToken(): string;
  setToken(token: string): boolean;
  clearToken(): boolean;
  voiceStart(): boolean;
  voiceStop(): boolean;
  overlayShow(): boolean;
  overlayHide(): boolean;
  engageEmergencyStop(): boolean;
}

declare global {
  interface Window {
    NexusBridge?: NexusNativeBridge;
  }
}

export interface ShellInfo {
  shell: 'android';
  bridgeVersion: number;
  appVersion: string;
  trustedOrigin: boolean;
  capabilities: string[];
}

function bridge(): NexusNativeBridge | undefined {
  return typeof window !== 'undefined' ? window.NexusBridge : undefined;
}

/** True when running inside the native shell with the bridge available. */
export function isNativeShell(): boolean {
  return bridge() !== undefined;
}

/** Parsed shell metadata, or null in a plain browser / on a malformed reply. */
export function shellInfo(): ShellInfo | null {
  const b = bridge();
  if (!b) return null;
  try {
    return JSON.parse(b.shellInfo()) as ShellInfo;
  } catch {
    return null;
  }
}

/**
 * The cockpit bearer token from the native secure store, or null when not in
 * the shell / unpaired. The native side hands it over only to a trusted
 * first-party origin; callers should seed the web config with it on boot so
 * the PWA and the app share one pairing.
 */
export function nativeToken(): string | null {
  const b = bridge();
  if (!b) return null;
  const t = b.getToken();
  return t.length > 0 ? t : null;
}

export function setNativeToken(token: string): boolean {
  return bridge()?.setToken(token) ?? false;
}

export function clearNativeToken(): boolean {
  return bridge()?.clearToken() ?? false;
}

export function voiceStart(): boolean {
  return bridge()?.voiceStart() ?? false;
}

export function voiceStop(): boolean {
  return bridge()?.voiceStop() ?? false;
}

export function overlayShow(): boolean {
  return bridge()?.overlayShow() ?? false;
}

export function overlayHide(): boolean {
  return bridge()?.overlayHide() ?? false;
}

/**
 * Engage the on-device emergency stop: the native side persists the engaged
 * flag (every mutation path reads it) and tears down the voice/overlay/work
 * services. Resuming requires an explicit, audited action — there is no silent
 * un-stop. Returns false in a plain browser.
 */
export function engageEmergencyStop(): boolean {
  return bridge()?.engageEmergencyStop() ?? false;
}
