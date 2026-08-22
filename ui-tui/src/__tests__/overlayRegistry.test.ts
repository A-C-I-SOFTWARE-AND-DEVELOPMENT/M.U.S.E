import { afterEach, describe, expect, it } from 'vitest'

import type { OverlayState } from '../app/interfaces.js'
import { BLOCKING_OVERLAY_IDS, FLOATING_OVERLAY_IDS, OVERLAY_IDS, STICKY_OVERLAY_IDS } from '../app/overlayRegistry.js'
import {
  $isBlocked,
  $isStatusRuleOccluded,
  getOverlayState,
  hasFloatingPanel,
  patchOverlayState,
  resetFlowOverlays,
  resetOverlayState
} from '../app/overlayStore.js'
import { patchUiState, resetUiState } from '../app/uiStore.js'

/**
 * Oracles copied VERBATIM from the hand-written structures OVERLAY_REGISTRY
 * replaced (overlayStore.ts / interfaces.ts / appOverlays.tsx, pre-registry).
 * They are the point of this file: the registry is only a safe swap while the
 * derived structures still equal these.
 */
const LEGACY_INITIAL_STATE = {
  agents: false,
  agentsInitialHistoryIndex: 0,
  approval: null,
  billing: null,
  clarify: null,
  confirm: null,
  ambient: [],
  widget: null,
  journey: false,
  modelPicker: false,
  pager: null,
  petPicker: false,
  pluginsHub: false,
  secret: null,
  sessions: false,
  skillsHub: false,
  subscription: null,
  sudo: null
}

/** The old `$isBlocked` destructure + boolean chain, in source order. */
const LEGACY_BLOCKING = [
  'agents',
  'approval',
  'billing',
  'clarify',
  'confirm',
  'journey',
  'modelPicker',
  'pager',
  'petPicker',
  'pluginsHub',
  'secret',
  'sessions',
  'skillsHub',
  'subscription',
  'sudo',
  'widget'
]

/** The old `hasFloatingPanel` chain. */
const LEGACY_FLOATING = ['modelPicker', 'pager', 'petPicker', 'pluginsHub', 'sessions', 'skillsHub']

/** The old `resetFlowOverlays` preserve list. */
const LEGACY_STICKY = [
  'agents',
  'agentsInitialHistoryIndex',
  'ambient',
  'widget',
  'journey',
  'modelPicker',
  'petPicker',
  'pluginsHub',
  'sessions',
  'skillsHub'
]

/**
 * The order the old `if (overlay.x) widgets.push(...)` chain in
 * FloatingOverlays pushed its panels — i.e. their on-screen stacking order.
 * FLOATING_OVERLAY_IDS is now that order, so it is asserted, not just its set.
 */
const LEGACY_PAINT_ORDER = ['sessions', 'modelPicker', 'petPicker', 'skillsHub', 'pluginsHub', 'pager']

/** A truthy "open" value for every overlay, keyed by id. */
const OPEN_VALUE: Record<string, unknown> = {
  agents: true,
  agentsInitialHistoryIndex: 3,
  ambient: [{ id: 'w' }],
  approval: { id: 'a' },
  billing: { screen: 'overview' },
  clarify: { id: 'c' },
  confirm: { id: 'c' },
  journey: true,
  modelPicker: true,
  pager: { lines: ['x'], offset: 0 },
  petPicker: true,
  pluginsHub: true,
  secret: { envVar: 'X' },
  sessions: true,
  skillsHub: true,
  subscription: { screen: 'overview' },
  sudo: { id: 's' },
  widget: { id: 'w' }
}

const openOnly = (id: string) => {
  resetOverlayState()
  patchOverlayState({ [id]: OPEN_VALUE[id] } as Partial<OverlayState>)
}

afterEach(() => {
  resetOverlayState()
  resetUiState()
})

describe('overlay registry — field set and initial values', () => {
  it('covers exactly the fields OverlayState used to declare by hand', () => {
    expect([...OVERLAY_IDS].sort()).toEqual(Object.keys(LEGACY_INITIAL_STATE).sort())
  })

  it('builds the same closed state the hardcoded initializer built', () => {
    resetOverlayState()
    expect(getOverlayState()).toEqual(LEGACY_INITIAL_STATE)
  })

  it('gives every build its own mutable seeds', () => {
    resetOverlayState()
    const first = getOverlayState()

    resetOverlayState()
    const second = getOverlayState()

    // `ambient: []` as a shared registry constant would alias every state.
    expect(second.ambient).not.toBe(first.ambient)
  })
})

describe('overlay registry — $isBlocked', () => {
  it('derives the same input set as the old destructure + chain', () => {
    expect([...BLOCKING_OVERLAY_IDS].sort()).toEqual([...LEGACY_BLOCKING].sort())
  })

  it('blocks for each blocking overlay and only those', () => {
    for (const id of OVERLAY_IDS) {
      openOnly(id)
      expect({ blocked: $isBlocked.get(), id }).toEqual({ blocked: LEGACY_BLOCKING.includes(id), id })
    }
  })

  it('is false on a freshly built state', () => {
    resetOverlayState()
    expect($isBlocked.get()).toBe(false)
  })
})

describe('overlay registry — hasFloatingPanel', () => {
  it('derives the same set as the old chain, in paint order', () => {
    expect(FLOATING_OVERLAY_IDS).toEqual(LEGACY_PAINT_ORDER)
    expect([...FLOATING_OVERLAY_IDS].sort()).toEqual([...LEGACY_FLOATING].sort())
  })

  it('matches the old chain for every overlay opened alone', () => {
    for (const id of OVERLAY_IDS) {
      openOnly(id)
      expect({ floating: hasFloatingPanel(getOverlayState()), id }).toEqual({
        floating: LEGACY_FLOATING.includes(id),
        id
      })
    }
  })

  it('still drives the top-statusbar occlusion gate', () => {
    patchUiState({ statusBar: 'top' })

    resetOverlayState()
    expect($isStatusRuleOccluded.get()).toBe(false)

    patchOverlayState({ skillsHub: true })
    expect($isStatusRuleOccluded.get()).toBe(true)
  })
})

describe('overlay registry — resetFlowOverlays', () => {
  it('derives the same preserve list the hardcoded reset spread', () => {
    expect([...STICKY_OVERLAY_IDS].sort()).toEqual([...LEGACY_STICKY].sort())
  })

  it('keeps user-toggled overlays and drops flow-scoped ones', () => {
    resetOverlayState()
    patchOverlayState(Object.fromEntries(OVERLAY_IDS.map(id => [id, OPEN_VALUE[id]])) as Partial<OverlayState>)

    const before = getOverlayState()
    resetFlowOverlays()
    const after = getOverlayState()

    for (const id of OVERLAY_IDS) {
      if (LEGACY_STICKY.includes(id)) {
        expect({ id, value: after[id] }).toEqual({ id, value: before[id] })
      } else {
        expect({ id, value: after[id] }).toEqual({
          id,
          value: LEGACY_INITIAL_STATE[id as keyof typeof LEGACY_INITIAL_STATE]
        })
      }
    }
  })

  it('closes the pager even though it is a floating panel', () => {
    // `floating` and `sticky` are independent axes; a pager is put up BY a
    // turn, so turn teardown must close it.
    openOnly('pager')
    resetFlowOverlays()
    expect(getOverlayState().pager).toBeNull()
  })
})
