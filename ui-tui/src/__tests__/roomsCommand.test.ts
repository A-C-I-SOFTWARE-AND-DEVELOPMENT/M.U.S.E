import { describe, expect, it } from 'vitest'

import type { OverlayState } from '../app/interfaces.js'
import { FLOATING_OVERLAY_IDS } from '../app/overlayRegistry.js'
import {
  $isBlocked,
  $overlayState,
  hasFloatingPanel,
  resetFlowOverlays,
  resetOverlayState
} from '../app/overlayStore.js'
import { findSlashCommand } from '../app/slash/registry.js'

/**
 * Guards the slash-command → overlay wiring end to end on the TUI side.
 *
 * The Fusion overlay shipped broken for exactly this reason: its component and
 * its slash command both existed, but the `OverlayState` field and the render
 * site did not, so the command set a flag nothing read and the panel could
 * never open. Nothing failed loudly.
 *
 * `OVERLAY_REGISTRY` closed most of that hole — the field, the initializer,
 * `$isBlocked`, `hasFloatingPanel()` and the sticky list are all derived from
 * one entry now, and the renderer table is a `Record<FloatingOverlayId, …>` so
 * the compiler demands a panel. The half that stays hand-written is the SLASH
 * COMMAND: nothing forces a registry entry to have a way in. That is what the
 * table below pins, for every floating panel and not just for `/rooms`.
 */

/** The command that opens each floating panel, and the argument that does it. */
const PANEL_COMMANDS: { arg: string; command: string; overlay: string }[] = [
  { arg: '', command: 'model', overlay: 'modelPicker' },
  { arg: 'list', command: 'pet', overlay: 'petPicker' },
  { arg: '', command: 'plugins', overlay: 'pluginsHub' },
  { arg: '', command: 'rooms', overlay: 'rooms' },
  { arg: '', command: 'sessions', overlay: 'sessions' },
  { arg: '', command: 'skills', overlay: 'skillsHub' }
]

/**
 * `pager` is the one floating panel with no command: a turn puts it up, the
 * user never asks for it. Every other one must be reachable by typing.
 */
const COMMANDLESS_PANELS = ['pager']

describe('every floating panel is reachable from the composer', () => {
  it('covers the whole floating set — a new panel must be added here on purpose', () => {
    expect([...PANEL_COMMANDS.map(c => c.overlay), ...COMMANDLESS_PANELS].sort()).toEqual(
      [...FLOATING_OVERLAY_IDS].sort()
    )
  })

  it.each(PANEL_COMMANDS)('/$command opens $overlay', ({ arg, command, overlay }) => {
    resetOverlayState()

    // The field EXISTS and starts closed. `toBe(false)` would not catch the
    // Fusion bug — reading a missing field also yields a falsy value — so the
    // key itself is asserted first.
    expect(Object.keys($overlayState.get())).toContain(overlay)
    expect($overlayState.get()[overlay as keyof OverlayState]).toBeFalsy()

    const cmd = findSlashCommand(command)

    expect(cmd).toBeDefined()

    // The command only flips state; the overlay host does the rendering.
    cmd?.run(arg, {} as never, `/${command} ${arg}`.trim())

    expect($overlayState.get()[overlay as keyof OverlayState]).toBeTruthy()

    // Without this the panel would be invisible even with the flag set:
    // FloatingOverlays returns null unless hasFloatingPanel() agrees there is
    // something to show.
    expect(hasFloatingPanel($overlayState.get())).toBe(true)

    // ...and the composer must stop taking keystrokes underneath it.
    expect($isBlocked.get()).toBe(true)

    // A panel the user opened deliberately survives turn teardown.
    resetFlowOverlays()
    expect($overlayState.get()[overlay as keyof OverlayState]).toBeTruthy()

    resetOverlayState()
    expect($overlayState.get()[overlay as keyof OverlayState]).toBeFalsy()
    expect($isBlocked.get()).toBe(false)
  })
})

describe('/rooms', () => {
  it('is registered', () => {
    expect(findSlashCommand('rooms')).toBeDefined()
  })

  it('does not squat on /boards, which already means kanban', () => {
    // `hermes kanban boards switch <slug>`, the `--board` flag and
    // `hermes_cli/kanban_db.py` own that noun. Answering `/boards` with a
    // roster editor would be the wrong surface for a real question.
    expect(findSlashCommand('boards')).toBeUndefined()
  })

  it('is case-insensitive, like every other slash command', () => {
    expect(findSlashCommand('ROOMS')).toBe(findSlashCommand('rooms'))
  })

  it('describes itself in the completion popover', () => {
    expect(findSlashCommand('rooms')?.help).toBeTruthy()
  })
})
