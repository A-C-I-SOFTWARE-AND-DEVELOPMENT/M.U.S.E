import { map } from 'nanostores'

/**
 * Wave-2 TUI-Fusion — agent-mode store (design.md 1.3B + Part-0 rule 8).
 *
 * Owns the Solo → MOA → Fusion cycle that Tab drives on an empty composer.
 * Deliberately separate from `uiStore` (owned by the Wave-3 integrator):
 * Wave-1 chrome (status badge, composer border/glyph, banner) reads this
 * store through the `globalThis.__museAgentMode` getter installed below —
 * the getter is the cross-wave contract from TUI-Foundation.
 */

export type AgentMode = 'fusion' | 'moa' | 'solo'

export interface AgentModeState {
  /** True once a gateway answered `fusion.status` with `available !== false`. */
  fusionAvailable: boolean
  /** True when the MOA tool can actually run (OPENROUTER key present per `fusion.status`). */
  moaAvailable: boolean
  mode: AgentMode
}

/** Snapshot returned by `globalThis.__museAgentMode` (all fields optional per chrome contract). */
export interface MuseAgentModeSnapshot {
  fusionAvailable?: boolean
  moaAvailable?: boolean
  mode?: AgentMode
  permission?: string
}

const MODE_CYCLE: readonly AgentMode[] = ['solo', 'moa', 'fusion']

const buildState = (): AgentModeState => ({
  fusionAvailable: false,
  mode: 'solo',
  moaAvailable: false
})

export const $agentMode = map<AgentModeState>(buildState())

/** Read the current snapshot outside React (keymap, chrome, tests). */
export const readAgentMode = (): AgentModeState => $agentMode.get()

export const setAgentMode = (mode: AgentMode) => {
  $agentMode.setKey('mode', mode)
}

/**
 * Cycle solo → moa → fusion → solo (design rule 8: modes are cycled, not
 * navigated). Unconditional per contract — availability flags are exposed so
 * chrome can dim/warn when the cycled-to mode is not backed by the gateway.
 */
export const cycleAgentMode = () => {
  const current = $agentMode.get().mode
  const idx = MODE_CYCLE.indexOf(current)
  const next = MODE_CYCLE[(idx + 1) % MODE_CYCLE.length] ?? 'solo'

  $agentMode.setKey('mode', next)
}

/**
 * Refresh availability flags after every successful `fusion.status` fetch
 * (called by fusionOverlay + the /fusion slash command). Never touches
 * `mode` — a stale mode is chrome's rendering problem, not a state rewrite.
 */
export const applyFusionAvailability = (
  status: { available?: boolean; moa?: { key_present?: boolean } } | null | undefined
) => {
  if (!status) {
    return
  }

  $agentMode.setKey('fusionAvailable', status.available !== false)
  $agentMode.setKey('moaAvailable', Boolean(status.moa?.key_present))
}

declare global {
  // Cross-wave chrome contract (TUI-Foundation): optional getter, optional fields.
   
  var __museAgentMode: (() => MuseAgentModeSnapshot) | undefined
}

// Install at module init so Wave-1 chrome lights up as soon as this store is
// imported anywhere in the app (fusionOverlay, /fusion command, keymap).
globalThis.__museAgentMode = (): MuseAgentModeSnapshot => {
  const s = $agentMode.get()

  return {
    fusionAvailable: s.fusionAvailable,
    moaAvailable: s.moaAvailable,
    mode: s.mode
  }
}
