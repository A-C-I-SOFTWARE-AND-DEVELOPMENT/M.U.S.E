'use client'

import { create } from 'zustand'
import type { MuseProject } from './types'

export type ModuleId =
  | 'mission'
  | 'pipeline'
  | 'narrative'
  | 'characters'
  | 'cinematographer'
  | 'world'
  | 'fidelity'
  | 'voice'
  | 'vision'
  | 'vault'
  | 'director'
  | 'sandbox'
  | 'gateway'

interface MuseState {
  activeModule: ModuleId
  activeProject: MuseProject | null
  projects: MuseProject[]
  setModule: (m: ModuleId) => void
  setActiveProject: (p: MuseProject | null) => void
  setProjects: (p: MuseProject[]) => void
  upsertProject: (p: MuseProject) => void
}

export const useMuse = create<MuseState>((set) => ({
  activeModule: 'mission',
  activeProject: null,
  projects: [],
  setModule: (m) => set({ activeModule: m }),
  setActiveProject: (p) => set({ activeProject: p }),
  setProjects: (p) => set({ projects: p }),
  upsertProject: (p) =>
    set((s) => {
      const exists = s.projects.some((x) => x.id === p.id)
      return {
        projects: exists ? s.projects.map((x) => (x.id === p.id ? p : x)) : [p, ...s.projects],
        activeProject: s.activeProject?.id === p.id ? p : s.activeProject,
      }
    }),
}))
