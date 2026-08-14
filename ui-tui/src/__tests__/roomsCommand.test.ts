import { describe, expect, it } from 'vitest'

import { $overlayState, hasFloatingPanel, resetOverlayState } from '../app/overlayStore.js'
import { findSlashCommand } from '../app/slash/registry.js'

/**
 * Guards the `/rooms` wiring end to end on the TUI side.
 *
 * The Fusion overlay shipped broken for exactly this reason: the component and
 * its slash command both existed, but the OverlayState field and the render
 * site did not, so `/fusion` set a flag nothing read and the panel could never
 * open. Nothing failed loudly. These assertions make that failure mode loud.
 */
describe('/rooms', () => {
  it('is registered, under its name and its alias', () => {
    expect(findSlashCommand('rooms')).toBeDefined()
    expect(findSlashCommand('boards')).toBe(findSlashCommand('rooms'))
  })

  it('opens the panel, and the host counts it as a floating panel', () => {
    resetOverlayState()
    expect($overlayState.get().rooms).toBe(false)

    // The command only flips state; the overlay host does the rendering.
    findSlashCommand('rooms')?.run('', {} as never)

    expect($overlayState.get().rooms).toBe(true)

    // Without this the panel would be invisible even with the flag set:
    // FloatingOverlays returns null unless hasFloatingPanel() agrees there is
    // something to show.
    expect(hasFloatingPanel($overlayState.get())).toBe(true)

    resetOverlayState()
    expect($overlayState.get().rooms).toBe(false)
  })

  it('blocks the composer while open, like every other modal panel', async () => {
    const { $isBlocked } = await import('../app/overlayStore.js')

    resetOverlayState()
    expect($isBlocked.get()).toBe(false)

    findSlashCommand('rooms')?.run('', {} as never)
    expect($isBlocked.get()).toBe(true)

    resetOverlayState()
  })
})
