import { patchOverlayState } from '../../overlayStore.js'
import type { SlashCommand } from '../types.js'

/**
 * `/rooms` — the Rooms panel.
 *
 * A room is a named, ordered roster kept per profile. They live in
 * `hermes_cli/rooms_db.py` and reach the TUI over the `rooms.*` gateway
 * methods; this command only opens the overlay, which then loads and edits.
 *
 * Deliberately NOT aliased to `/boards`. A board here is a KANBAN board
 * (`hermes_cli/kanban_db.py`, `hermes kanban boards switch <slug>`, the
 * `--board` flag): a root-anchored, profile-shared task DB with nothing to do
 * with a roster. Answering `/boards` with this panel would be the wrong surface
 * for a real question.
 */
export const roomsCommands: SlashCommand[] = [
  {
    help: 'browse and edit rooms — named rosters',
    name: 'rooms',
    run: () => {
      patchOverlayState({ rooms: true })
    }
  }
]
