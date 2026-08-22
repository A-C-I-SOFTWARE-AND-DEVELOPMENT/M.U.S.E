import type { ActiveWidget } from '../sdk/types.js'
import type { ApprovalReq, ClarifyReq, ConfirmReq, SecretReq, SudoReq } from '../types.js'

import type { BillingOverlayState, PagerState, SubscriptionOverlayState } from './interfaces.js'

/**
 * Single source of truth for the overlay surfaces.
 *
 * Adding an overlay used to mean five hand-edits that had to agree with each
 * other: a field on `OverlayState`, a key in `buildOverlayState()`, a name in
 * BOTH halves of `$isBlocked` (destructure + boolean chain), a name in
 * `hasFloatingPanel()`, a name in `resetFlowOverlays()`'s preserve list, and a
 * `widgets.push()` block in `appOverlays.tsx`. Miss one and the failure is
 * quiet — a panel that never opens, or one that opens and leaves the composer
 * accepting keystrokes underneath it.
 *
 * Now every one of those is DERIVED from the entries below. Adding an overlay
 * is one entry here, plus its renderer in `FLOATING_OVERLAY_RENDERERS`
 * (`appOverlays.tsx`) if it draws a floating panel — and the compiler requires
 * that renderer, so it cannot be forgotten.
 *
 * DECLARATION ORDER IS SIGNIFICANT for `floating` entries: it is the order the
 * panels are pushed into the FloatingOverlays grid, i.e. their stacking order
 * on screen. Non-floating entries can be declared anywhere.
 */
export interface OverlayDef<V> {
  /**
   * True while the overlay suspends composer input (`$isBlocked`). Note this
   * is NOT the same question as "does it paint over the status rule" — see
   * `$isStatusRuleOccluded` in overlayStore.ts.
   */
  blocks: boolean
  /** Renders as a panel in the FloatingOverlays grid (`hasFloatingPanel`). */
  floating: boolean
  /**
   * The closed/empty value. A FACTORY, not a constant: `buildOverlayState()`
   * runs on every reset, and a shared mutable seed (`ambient: []`) would alias
   * every state object built from it.
   */
  initial: () => V
  /**
   * True when the overlay survives `resetFlowOverlays()` — user-toggled
   * surfaces the user opened deliberately (the agents dashboard, the model
   * picker, the hubs) rather than flow-scoped prompts a turn put up. Turn
   * teardown must not close what the user opened.
   */
  sticky: boolean
}

const defineOverlay = <const D extends OverlayDef<unknown>>(def: D): D => def

export const OVERLAY_REGISTRY = {
  // ── Turn-scoped surfaces the ComposerPane unmounts around ──
  agents: defineOverlay({
    blocks: true,
    floating: false,
    initial: (): boolean => false,
    sticky: true
  }),
  /**
   * Companion field of `agents`, not an overlay of its own: which history
   * entry the dashboard opens on. Declared here so `OverlayState` and the
   * reset helpers stay single-sourced rather than half-derived.
   */
  agentsInitialHistoryIndex: defineOverlay({
    blocks: false,
    floating: false,
    initial: (): number => 0,
    sticky: true
  }),
  journey: defineOverlay({
    blocks: true,
    floating: false,
    initial: (): boolean => false,
    sticky: true
  }),

  // ── PromptZone flow states: rendered in normal flow above the composer ──
  approval: defineOverlay({
    blocks: true,
    floating: false,
    initial: (): ApprovalReq | null => null,
    sticky: false
  }),
  billing: defineOverlay({
    blocks: true,
    floating: false,
    initial: (): BillingOverlayState | null => null,
    sticky: false
  }),
  clarify: defineOverlay({
    blocks: true,
    floating: false,
    initial: (): ClarifyReq | null => null,
    sticky: false
  }),
  confirm: defineOverlay({
    blocks: true,
    floating: false,
    initial: (): ConfirmReq | null => null,
    sticky: false
  }),
  secret: defineOverlay({
    blocks: true,
    floating: false,
    initial: (): SecretReq | null => null,
    sticky: false
  }),
  subscription: defineOverlay({
    blocks: true,
    floating: false,
    initial: (): SubscriptionOverlayState | null => null,
    sticky: false
  }),
  sudo: defineOverlay({
    blocks: true,
    floating: false,
    initial: (): SudoReq | null => null,
    sticky: false
  }),

  // ── Widget apps ──
  /** Ambient widget apps — glanceable dock, non-blocking (never in $isBlocked). */
  ambient: defineOverlay({
    blocks: false,
    floating: false,
    initial: (): ActiveWidget[] => [],
    sticky: true
  }),
  /** Modal widget app — owns input, blocks the composer. */
  widget: defineOverlay({
    blocks: true,
    floating: false,
    initial: (): ActiveWidget | null => null,
    sticky: true
  }),

  // ── Floating panels. ORDER BELOW IS THE ON-SCREEN STACKING ORDER. ──
  sessions: defineOverlay({
    blocks: true,
    floating: true,
    initial: (): boolean => false,
    sticky: true
  }),
  modelPicker: defineOverlay({
    blocks: true,
    floating: true,
    initial: (): boolean | { refresh?: boolean } => false,
    sticky: true
  }),
  petPicker: defineOverlay({
    blocks: true,
    floating: true,
    initial: (): boolean => false,
    sticky: true
  }),
  skillsHub: defineOverlay({
    blocks: true,
    floating: true,
    initial: (): boolean => false,
    sticky: true
  }),
  pluginsHub: defineOverlay({
    blocks: true,
    floating: true,
    initial: (): boolean => false,
    sticky: true
  }),
  /**
   * Flow-scoped despite being floating: a pager is put up BY a turn, so turn
   * teardown closes it. `floating` and `sticky` are independent axes.
   */
  pager: defineOverlay({
    blocks: true,
    floating: true,
    initial: (): PagerState | null => null,
    sticky: false
  })
}

export type OverlayRegistry = typeof OVERLAY_REGISTRY

export type OverlayId = keyof OverlayRegistry

/** The overlay slice of `OverlayState`, one field per registry entry. */
export type OverlayRegistryState = {
  [K in OverlayId]: ReturnType<OverlayRegistry[K]['initial']>
}

/** Ids of entries with `floating: true` — the FloatingOverlays panel set. */
export type FloatingOverlayId = {
  [K in OverlayId]: OverlayRegistry[K]['floating'] extends true ? K : never
}[OverlayId]

/**
 * Registry ids in declaration order. Object key order is insertion order for
 * string keys, and this is the order floating panels stack, so it is read
 * once here rather than re-derived at each use site.
 */
export const OVERLAY_IDS = Object.keys(OVERLAY_REGISTRY) as OverlayId[]

const idsWhere = (pick: (def: OverlayDef<unknown>) => boolean) => OVERLAY_IDS.filter(id => pick(OVERLAY_REGISTRY[id]))

/** Ids that suspend composer input — the `$isBlocked` inputs. */
export const BLOCKING_OVERLAY_IDS = idsWhere(def => def.blocks)

/** Ids that draw a floating panel — the `hasFloatingPanel` inputs, in paint order. */
export const FLOATING_OVERLAY_IDS = idsWhere(def => def.floating) as FloatingOverlayId[]

/** Ids `resetFlowOverlays()` carries across a turn boundary. */
export const STICKY_OVERLAY_IDS = idsWhere(def => def.sticky)
