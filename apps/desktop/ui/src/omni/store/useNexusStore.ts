import { create } from 'zustand';
import type {
  FusionStrategy,
  GateConfig,
  SteeringVector,
  VertexDef,
} from '@/lib/types';
import { DEFAULT_PRESET, VERTEX_PRESETS } from '@/lib/vertices';
import { balancedWeights } from '@/lib/steering';
import { defaultGateConfig } from '@/lib/fusion';
import type { FusionDef, FusionRun } from '@/lib/fusionTypes';

const FUSION_LS = 'nexus.fusion.v1';
function loadFusion(): { saved: FusionDef[]; history: FusionRun[]; favorites: string[] } {
  try {
    const s = JSON.parse(localStorage.getItem(FUSION_LS) ?? '{}');
    return { saved: s.saved ?? [], history: s.history ?? [], favorites: s.favorites ?? [] };
  } catch {
    return { saved: [], history: [], favorites: [] };
  }
}
function persistFusion(s: { saved: FusionDef[]; history: FusionRun[]; favorites: string[] }) {
  try {
    localStorage.setItem(FUSION_LS, JSON.stringify({ saved: s.saved, history: s.history.slice(0, 100), favorites: s.favorites }));
  } catch {
    /* ignore */
  }
}

export interface SteeringProfile {
  id: string;
  name: string;
  presetKey: string;
  locked: boolean;
  /** Last emitted vector for this profile (null until first interaction). */
  vector: SteeringVector | null;
}

interface NexusState {
  presetKey: string;
  vertices: VertexDef[];
  profiles: SteeringProfile[];
  activeProfileId: string;
  lastVector: SteeringVector | null;

  // Axiom Gate / fusion state (persists across tab switches).
  fusionStrategy: FusionStrategy;
  gateConfig: GateConfig;
  sourceContrib: Record<string, number>;

  // Observatory wallpaper ("mirror") mode — hides chrome, full-bleed galaxy.
  wallpaper: boolean;

  // Fusion Gate: saved fusions, run history, favorites.
  savedFusions: FusionDef[];
  fusionHistory: FusionRun[];
  fusionFavorites: string[];

  setPreset: (key: string) => void;
  setActiveProfile: (id: string) => void;
  addProfile: (name: string) => void;
  toggleLock: (id: string) => void;
  emitVector: (v: SteeringVector) => void;

  setFusionStrategy: (s: FusionStrategy) => void;
  toggleGate: (key: keyof GateConfig['enforced']) => void;
  setOwnerApproved: (v: boolean) => void;
  setSourceContrib: (id: string, value: number) => void;

  setWallpaper: (v: boolean) => void;

  saveFusion: (f: FusionDef) => void;
  deleteFusion: (id: string) => void;
  toggleFusionFavorite: (id: string) => void;
  addFusionRun: (r: FusionRun) => void;
}

const initialProfile: SteeringProfile = {
  id: 'default',
  name: 'Default',
  presetKey: 'default',
  locked: false,
  vector: null,
};

export const useNexusStore = create<NexusState>((set) => ({
  presetKey: 'default',
  vertices: DEFAULT_PRESET,
  profiles: [initialProfile],
  activeProfileId: 'default',
  lastVector: null,

  fusionStrategy: 'weighted-mean',
  gateConfig: defaultGateConfig(),
  sourceContrib: {},

  wallpaper:
    typeof window !== 'undefined' && new URLSearchParams(window.location.search).get('wallpaper') === '1',

  ...(() => {
    const f = typeof localStorage !== 'undefined' ? loadFusion() : { saved: [], history: [], favorites: [] };
    return { savedFusions: f.saved, fusionHistory: f.history, fusionFavorites: f.favorites };
  })(),

  setPreset: (key) =>
    set(() => ({
      presetKey: key,
      vertices: VERTEX_PRESETS[key] ?? DEFAULT_PRESET,
    })),

  setActiveProfile: (id) => set({ activeProfileId: id }),

  addProfile: (name) =>
    set((s) => {
      const id = `p_${Date.now().toString(36)}`;
      return {
        profiles: [
          ...s.profiles,
          { id, name, presetKey: s.presetKey, locked: false, vector: null },
        ],
        activeProfileId: id,
      };
    }),

  toggleLock: (id) =>
    set((s) => ({
      profiles: s.profiles.map((p) =>
        p.id === id ? { ...p, locked: !p.locked } : p,
      ),
    })),

  emitVector: (v) =>
    set((s) => ({
      lastVector: v,
      profiles: s.profiles.map((p) =>
        p.id === v.profileId ? { ...p, vector: v } : p,
      ),
    })),

  setFusionStrategy: (fusionStrategy) => set({ fusionStrategy }),

  toggleGate: (key) =>
    set((s) => ({
      gateConfig: {
        ...s.gateConfig,
        enforced: { ...s.gateConfig.enforced, [key]: !s.gateConfig.enforced[key] },
      },
    })),

  setOwnerApproved: (v) =>
    set((s) => ({ gateConfig: { ...s.gateConfig, ownerApproved: v } })),

  setSourceContrib: (id, value) =>
    set((s) => ({ sourceContrib: { ...s.sourceContrib, [id]: value } })),

  setWallpaper: (wallpaper) => set({ wallpaper }),

  saveFusion: (f) =>
    set((s) => {
      const saved = [f, ...s.savedFusions.filter((x) => x.id !== f.id)];
      const next = { saved, history: s.fusionHistory, favorites: s.fusionFavorites };
      persistFusion(next);
      return { savedFusions: saved };
    }),

  deleteFusion: (id) =>
    set((s) => {
      const saved = s.savedFusions.filter((x) => x.id !== id);
      const favorites = s.fusionFavorites.filter((x) => x !== id);
      persistFusion({ saved, history: s.fusionHistory, favorites });
      return { savedFusions: saved, fusionFavorites: favorites };
    }),

  toggleFusionFavorite: (id) =>
    set((s) => {
      const favorites = s.fusionFavorites.includes(id)
        ? s.fusionFavorites.filter((x) => x !== id)
        : [...s.fusionFavorites, id];
      persistFusion({ saved: s.savedFusions, history: s.fusionHistory, favorites });
      return { fusionFavorites: favorites };
    }),

  addFusionRun: (r) =>
    set((s) => {
      const history = [r, ...s.fusionHistory].slice(0, 100);
      persistFusion({ saved: s.savedFusions, history, favorites: s.fusionFavorites });
      return { fusionHistory: history };
    }),
}));

// Helper for default neutral display.
export const neutralBaseline = (vertices: VertexDef[]) => balancedWeights(vertices);
