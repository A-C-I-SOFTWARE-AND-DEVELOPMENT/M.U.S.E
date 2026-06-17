import { create } from 'zustand';
import type { SteeringVector, VertexDef } from '@/lib/types';
import { DEFAULT_PRESET, VERTEX_PRESETS } from '@/lib/vertices';
import { balancedWeights } from '@/lib/steering';

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

  setPreset: (key: string) => void;
  setActiveProfile: (id: string) => void;
  addProfile: (name: string) => void;
  toggleLock: (id: string) => void;
  emitVector: (v: SteeringVector) => void;
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
}));

// Helper for default neutral display.
export const neutralBaseline = (vertices: VertexDef[]) => balancedWeights(vertices);
