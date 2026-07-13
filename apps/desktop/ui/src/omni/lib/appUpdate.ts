// ============================================================================
// PWA self-update store. NEXUS is served from GitHub Pages built off MUSE `main`,
// so "pull the latest from git" in the browser means: activate the newest service
// worker and reload. main.tsx registers the SW via virtual:pwa-register (kept out
// of this module so it stays unit-testable / vitest-resolvable) and hands us the
// `updateSW` callback. The UI subscribes here to show a one-click "Update NEXUS".
// ============================================================================

export type UpdateFn = (reloadPage?: boolean) => Promise<void> | void;

export interface UpdateState {
  needRefresh: boolean; // a new build is waiting
  offlineReady: boolean; // first install cached for offline
  checking: boolean;
}

let state: UpdateState = { needRefresh: false, offlineReady: false, checking: false };
let updateFn: UpdateFn | null = null;
const subs = new Set<() => void>();

function set(patch: Partial<UpdateState>) {
  state = { ...state, ...patch };
  subs.forEach((f) => f());
}

/** Called once from main.tsx with the updateSW handle from virtual:pwa-register. */
export function registerUpdater(fn: UpdateFn): void {
  updateFn = fn;
}

export function markNeedRefresh(): void {
  set({ needRefresh: true, checking: false });
}
export function markOfflineReady(): void {
  set({ offlineReady: true });
}

export function getUpdateState(): UpdateState {
  return state;
}

export function subscribeUpdate(fn: () => void): () => void {
  subs.add(fn);
  return () => subs.delete(fn);
}

/** One-click update: activate the waiting SW and reload to the latest main build. */
export async function applyUpdate(): Promise<void> {
  if (updateFn) {
    await updateFn(true);
  } else if (typeof location !== 'undefined') {
    location.reload();
  }
}

/** Ask the browser to re-check the server for a newer service worker. */
export async function checkForUpdate(): Promise<void> {
  set({ checking: true });
  try {
    if (typeof navigator !== 'undefined' && 'serviceWorker' in navigator) {
      const reg = await navigator.serviceWorker.getRegistration();
      await reg?.update();
    }
    if (updateFn) await updateFn(false);
  } catch {
    /* ignore — offline or no SW */
  } finally {
    set({ checking: false });
  }
}
