import { create } from 'zustand';
import { authHeaders, museBase } from '@/lib/config';
import { UniverseApiError, UniverseClient } from './client.ts';
import type {
  ApiProblem,
  CommandResult,
  PlayerMode,
  UniverseCatalogSnapshot,
  UniverseCommand,
  UniverseSnapshot,
} from './types.ts';
import type { FidelityPreference, FidelityTier } from './fidelity.ts';

export type UniverseConnection =
  | 'idle'
  | 'loading'
  | 'online'
  | 'empty'
  | 'offline'
  | 'denied'
  | 'conflict'
  | 'degraded'
  | 'error';

export interface UniversePreferences {
  fidelity: FidelityPreference;
  depthStrength: number;
  reducedMotion: boolean;
  particleDensity: number;
  comfortVignette: number;
  textScale: number;
  captions: boolean;
  colorSafe: boolean;
  twoDOnly: boolean;
}

export interface RenderDiagnostics {
  tier: FidelityTier | 'not-mounted';
  dpr: number | null;
  frameTimeMs: number | null;
  drawCalls: number | null;
  triangles: number | null;
  textureMemoryMb: number | null;
  graphNodeCount: number | null;
  lastEventCursor: number;
  degradedReasons: string[];
}

interface UniverseState {
  realmId: string;
  snapshot: UniverseSnapshot | null;
  catalog: UniverseCatalogSnapshot | null;
  cursor: number;
  connection: UniverseConnection;
  problem: ApiProblem | null;
  selected: string | null;
  playerMode: PlayerMode;
  preferences: UniversePreferences;
  staleAt: string | null;
  lastAcknowledgedAt: string | null;
  diagnostics: RenderDiagnostics;
  connect: (realmId?: string) => Promise<void>;
  refresh: () => Promise<void>;
  disconnect: () => void;
  select: (id: string | null) => void;
  setPlayerMode: (mode: PlayerMode) => void;
  setPreferences: (patch: Partial<UniversePreferences>) => void;
  reportDiagnostics: (patch: Partial<RenderDiagnostics>) => void;
  executeCommand: (command: UniverseCommand) => Promise<CommandResult>;
  validateCommand: (command: UniverseCommand) => Promise<Record<string, unknown>>;
}

const PREFERENCES_KEY = 'muse.universe.preferences.v1';
const DEFAULT_PREFERENCES: UniversePreferences = {
  fidelity: 'auto',
  depthStrength: 0.72,
  reducedMotion:
    typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches,
  particleDensity: 0.72,
  comfortVignette: 0.42,
  textScale: 1,
  captions: true,
  colorSafe: false,
  twoDOnly: false,
};

function loadPreferences(): UniversePreferences {
  if (typeof localStorage === 'undefined') return DEFAULT_PREFERENCES;
  try {
    const value = JSON.parse(localStorage.getItem(PREFERENCES_KEY) ?? '{}') as Partial<UniversePreferences>;
    return { ...DEFAULT_PREFERENCES, ...value };
  } catch {
    return DEFAULT_PREFERENCES;
  }
}

function persistPreferences(preferences: UniversePreferences): void {
  try {
    localStorage.setItem(PREFERENCES_KEY, JSON.stringify(preferences));
  } catch {
    // Preferences are non-sensitive; storage can still be unavailable.
  }
}

function toProblem(error: UniverseApiError): ApiProblem {
  return {
    kind: error.kind,
    status: error.status,
    message: error.message,
    correlationId: error.correlationId,
    currentVersion: error.currentVersion,
    retryAfterMs: error.retryAfterMs,
    occurredAt: new Date().toISOString(),
  };
}

function stateForError(error: UniverseApiError): UniverseConnection {
  if (error.kind === 'unauthenticated' || error.kind === 'denied') return 'denied';
  if (error.kind === 'conflict') return 'conflict';
  if (error.kind === 'network') return 'offline';
  if (error.kind === 'server' || error.kind === 'rate-limited' || error.kind === 'unavailable') {
    return 'degraded';
  }
  return 'error';
}

function hasProjectedEntities(snapshot: UniverseSnapshot): boolean {
  return Object.values(snapshot).some(
    (value) => Array.isArray(value) && value.some((entry) => entry && typeof entry === 'object'),
  );
}

function withViewerEvidence(snapshot: UniverseSnapshot, actorId: string, realmId: string): UniverseSnapshot {
  if (snapshot.viewer) return snapshot;
  const realms = Array.isArray(snapshot.realms) ? snapshot.realms : [];
  const players = Array.isArray(snapshot.players) ? snapshot.players : [];
  const realm = realms.find((entry) => entry.id === (snapshot.realm_id ?? realmId));
  const player = players.find((entry) => entry.id === actorId);
  if (realm?.owner_id !== actorId && !player) return snapshot;
  const displayName = player && typeof player.display_name === 'string'
    ? player.display_name
    : player?.name;
  return {
    ...snapshot,
    viewer: {
      actor_id: actorId,
      display_name: typeof displayName === 'string' ? displayName : undefined,
      scopes: [],
      realm_role: realm?.owner_id === actorId ? 'owner' : 'member',
    },
  };
}

let client: UniverseClient | null = null;
let controller: AbortController | null = null;
let pollTimer: number | null = null;
let generation = 0;

function clearRuntime(): void {
  generation += 1;
  controller?.abort();
  controller = null;
  client = null;
  if (pollTimer != null) window.clearTimeout(pollTimer);
  pollTimer = null;
}

export const useUniverseStore = create<UniverseState>((set, get) => {
  const schedulePoll = (activeGeneration: number, attempt = 0): void => {
    if (activeGeneration !== generation || !client || !controller) return;
    const delay = attempt === 0 ? 1200 : Math.min(30_000, 1000 * 2 ** Math.min(attempt, 5));
    const jitter = Math.round(delay * (0.08 + Math.random() * 0.12));
    pollTimer = window.setTimeout(async () => {
      if (activeGeneration !== generation || !client || !controller) return;
      try {
        const page = await client.events(
          get().realmId,
          get().cursor,
          controller.signal,
        );
        if (activeGeneration !== generation) return;
        set((state) => ({
          cursor: Math.max(state.cursor, page.cursor),
          problem: null,
          lastAcknowledgedAt: new Date().toISOString(),
          diagnostics: { ...state.diagnostics, lastEventCursor: Math.max(state.cursor, page.cursor) },
        }));
        if (page.events.length > 0) await get().refresh();
        schedulePoll(activeGeneration, 0);
      } catch (error) {
        if (error instanceof DOMException && error.name === 'AbortError') return;
        const apiError =
          error instanceof UniverseApiError
            ? error
            : new UniverseApiError('network', 'Universe event stream was interrupted.', { cause: error });
        set((state) => ({
          connection: stateForError(apiError),
          problem: toProblem(apiError),
          staleAt: state.snapshot ? new Date().toISOString() : null,
          diagnostics: {
            ...state.diagnostics,
            degradedReasons: Array.from(new Set([...state.diagnostics.degradedReasons, apiError.kind])),
          },
        }));
        if (apiError.kind !== 'denied' && apiError.kind !== 'conflict') {
          schedulePoll(activeGeneration, attempt + 1);
        }
      }
    }, delay + jitter);
  };

  return {
    realmId: 'rlm_local',
    snapshot: null,
    catalog: null,
    cursor: 0,
    connection: 'idle',
    problem: null,
    selected: null,
    playerMode: 'walk',
    preferences: loadPreferences(),
    staleAt: null,
    lastAcknowledgedAt: null,
    diagnostics: {
      tier: 'not-mounted',
      dpr: null,
      frameTimeMs: null,
      drawCalls: null,
      triangles: null,
      textureMemoryMb: null,
      graphNodeCount: null,
      lastEventCursor: 0,
      degradedReasons: [],
    },

    connect: async (realmId = get().realmId) => {
      clearRuntime();
      const activeGeneration = generation;
      const base = museBase();
      const headers = authHeaders();
      set({ realmId, connection: 'loading', problem: null, staleAt: null });
      if (!base) {
        const error = new UniverseApiError('unavailable', 'No M.U.S.E. gateway is configured.');
        set({ connection: 'degraded', problem: toProblem(error) });
        return;
      }
      if (!headers.Authorization) {
        const error = new UniverseApiError('unauthenticated', 'This device is not paired with the gateway.');
        set({ connection: 'denied', problem: toProblem(error) });
        return;
      }

      controller = new AbortController();
      client = new UniverseClient(base, authHeaders);
      try {
        const responseSnapshot = await client.snapshot(realmId, controller.signal);
        if (activeGeneration !== generation) return;
        const snapshot = withViewerEvidence(responseSnapshot, client.actorId, realmId);
        let catalog: UniverseCatalogSnapshot | null = null;
        try {
          catalog = await client.catalog(controller.signal);
        } catch {
          // Catalog absence degrades customization only; the snapshot remains authoritative.
        }
        const cursor =
          typeof snapshot.cursor === 'number' && Number.isFinite(snapshot.cursor)
            ? snapshot.cursor
            : 0;
        const acknowledged = new Date().toISOString();
        set((state) => ({
          snapshot,
          catalog,
          cursor,
          connection: hasProjectedEntities(snapshot) ? 'online' : 'empty',
          problem: null,
          staleAt: null,
          lastAcknowledgedAt: acknowledged,
          diagnostics: {
            ...state.diagnostics,
            lastEventCursor: cursor,
            degradedReasons: catalog ? state.diagnostics.degradedReasons : ['catalog-unavailable'],
          },
        }));
        schedulePoll(activeGeneration);
      } catch (error) {
        if (error instanceof DOMException && error.name === 'AbortError') return;
        const apiError =
          error instanceof UniverseApiError
            ? error
            : new UniverseApiError('network', 'Universe connection failed.', { cause: error });
        set({ connection: stateForError(apiError), problem: toProblem(apiError) });
      }
    },

    refresh: async () => {
      if (!client || !controller) {
        await get().connect();
        return;
      }
      try {
        const responseSnapshot = await client.snapshot(get().realmId, controller.signal);
        const snapshot = withViewerEvidence(responseSnapshot, client.actorId, get().realmId);
        set({
          snapshot,
          connection: hasProjectedEntities(snapshot) ? 'online' : 'empty',
          problem: null,
          staleAt: null,
          lastAcknowledgedAt: new Date().toISOString(),
        });
      } catch (error) {
        if (error instanceof DOMException && error.name === 'AbortError') return;
        const apiError =
          error instanceof UniverseApiError
            ? error
            : new UniverseApiError('network', 'Universe refresh failed.', { cause: error });
        set((state) => ({
          connection: stateForError(apiError),
          problem: toProblem(apiError),
          staleAt: state.snapshot ? new Date().toISOString() : null,
        }));
        throw apiError;
      }
    },

    disconnect: () => {
      clearRuntime();
      set((state) => ({
        connection: 'idle',
        staleAt: state.snapshot ? new Date().toISOString() : null,
      }));
    },

    select: (selected) => set({ selected }),
    setPlayerMode: (playerMode) => set({ playerMode }),
    setPreferences: (patch) =>
      set((state) => {
        const preferences = { ...state.preferences, ...patch };
        persistPreferences(preferences);
        return { preferences };
      }),
    reportDiagnostics: (patch) =>
      set((state) => ({ diagnostics: { ...state.diagnostics, ...patch } })),

    executeCommand: async (command) => {
      if (!client || !controller) {
        throw new UniverseApiError('unavailable', 'Universe command service is not connected.');
      }
      try {
        const result = await client.command(command, controller.signal);
        await get().refresh();
        return result;
      } catch (error) {
        const apiError =
          error instanceof UniverseApiError
            ? error
            : new UniverseApiError('network', 'Universe command failed.', { cause: error });
        set({ connection: stateForError(apiError), problem: toProblem(apiError) });
        throw apiError;
      }
    },

    validateCommand: async (command) => {
      if (!client || !controller) {
        throw new UniverseApiError('unavailable', 'Universe validation service is not connected.');
      }
      return client.validate(command, controller.signal);
    },
  };
});
