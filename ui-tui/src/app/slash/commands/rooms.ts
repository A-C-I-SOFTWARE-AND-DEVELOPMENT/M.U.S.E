import { patchOverlayState } from '../../overlayStore.js'
import type { SlashCommand } from '../types.js'

/**
 * `/rooms` — the Rooms panel.
 *
 * A room is a named board of agents with a mixture describing how they work
 * the problem (council / experts / agents). They live in
 * ``hermes_cli/rooms_db.py`` and reach the TUI over the ``rooms.*`` gateway
 * methods; the panel itself only opens the overlay, which then loads.
 */
export const roomsCommands: SlashCommand[] = [
  {
    aliases: ['boards'],
    help: 'browse rooms — named boards of agents',
    name: 'rooms',
    run: () => {
      patchOverlayState({ rooms: true })
    }
  }
]
