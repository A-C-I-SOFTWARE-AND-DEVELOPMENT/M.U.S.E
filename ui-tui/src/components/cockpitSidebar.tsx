import { Box, Text, useStdout } from '@hermes/ink'
import { useEffect, useState } from 'react'

import { useGateway } from '../app/gatewayContext.js'
import { $uiState } from '../app/uiStore.js'
import type { Theme } from '../theme.js'

import { readMuseAgentMode } from './appChrome.js'

/**
 * The cockpit's left sidebar, in the terminal.
 *
 * Mirrors the muse cockpit: the brand mark on top, the six ways to work, the
 * rooms you can ask, and recent conversations. Every section is fed by the
 * gateway the TUI already speaks to — `rooms.list` and `session.list` — so
 * nothing here is decoration standing in for data.
 *
 * Collapses below {@link HIDE_BELOW} columns rather than squeezing the
 * transcript: a chat pane narrower than ~60 columns is worse than no sidebar.
 */

export const SIDEBAR_WIDTH = 26
const HIDE_BELOW = SIDEBAR_WIDTH + 60

/**
 * Columns the sidebar takes out of the terminal, given its total width.
 *
 * Pure and dependency-free so the layout can subtract it at the single place
 * the usable width is decided (`useMainApp`). Every surface — banner, session
 * panel, transcript, composer — derives from that one number, so anything that
 * measured the raw terminal width would render into space the sidebar owns and
 * spill off the right edge.
 */
export function sidebarColumns(totalCols: number): number {
  return totalCols >= HIDE_BELOW ? SIDEBAR_WIDTH : 0
}

/** Terminal width minus whatever the sidebar reserves. */
export function usableColumns(totalCols: number): number {
  return Math.max(1, totalCols - sidebarColumns(totalCols))
}

/** muse's six modes — the cockpit's "Ways to work". */
const WAYS = ['Companion', 'Strategy', 'Critic', 'Operator', 'Builder', 'Voice'] as const

const MAX_ROOMS = 5
const MAX_CONVERSATIONS = 5

interface RoomRow {
  id: string
  memberIds?: string[]
  name: string
}

interface SessionRow {
  id: string
  preview?: string
  title?: string
}

export function useSidebarVisible(): boolean {
  const { stdout } = useStdout()

  return sidebarColumns(stdout?.columns ?? 80) > 0
}

export function CockpitSidebar({ t }: { t: Theme }) {
  const { gw } = useGateway()
  const [rooms, setRooms] = useState<RoomRow[]>([])
  const [sessions, setSessions] = useState<SessionRow[]>([])

  useEffect(() => {
    let disposed = false

    // Both are optional surfaces: a gateway without them (or a profile with an
    // unreadable store) should leave the section empty, never break the shell
    // the transcript lives in.
    gw.request<{ rooms?: RoomRow[] }>('rooms.list', {})
      .then(r => {
        if (!disposed) setRooms(r?.rooms ?? [])
      })
      .catch(() => {})

    gw.request<{ sessions?: SessionRow[] }>('session.list', {})
      .then(r => {
        if (!disposed) setSessions(r?.sessions ?? [])
      })
      .catch(() => {})

    return () => {
      disposed = true
    }
  }, [gw])

  const label = (text: string) => (
    <Text color={t.color.faint}>
      {text}
      {'  '}
    </Text>
  )

  return (
    <Box flexDirection="column" flexShrink={0} paddingX={1} width={SIDEBAR_WIDTH}>
      <Text>
        <Text color={t.color.accent}>{t.brand.icon} </Text>
        <Text bold color={t.color.primary}>
          m u s e
        </Text>
      </Text>

      <Text />
      {label('Ways to work')}
      {WAYS.map(way => (
        <Text color={t.color.text} key={way} wrap="truncate-end">
          {'  '}
          {way}
        </Text>
      ))}

      <Text />
      {label('Rooms')}
      {rooms.length ? (
        rooms.slice(0, MAX_ROOMS).map(room => (
          <Text color={t.color.text} key={room.id} wrap="truncate-end">
            {'  '}
            {room.name}
            <Text color={t.color.faint}>
              {'  '}
              {room.memberIds?.length ?? 0}
            </Text>
          </Text>
        ))
      ) : (
        <Text color={t.color.faint}>{'  '}none</Text>
      )}

      <Text />
      {label('Conversations')}
      {sessions.length ? (
        sessions.slice(0, MAX_CONVERSATIONS).map(session => (
          <Text color={t.color.muted} key={session.id} wrap="truncate-end">
            {'  '}
            {(session.title || session.preview || session.id).trim()}
          </Text>
        ))
      ) : (
        <Text color={t.color.faint}>{'  '}No conversations yet.</Text>
      )}

      <Box flexGrow={1} />
      <Text color={t.color.faint} wrap="truncate-end">
        ^P palette
      </Text>
    </Box>
  )
}

/**
 * The cockpit's chip row: which way of working is live right now.
 *
 * `Tab` on an empty composer cycles Solo → MOA → Fusion. That cycle used to
 * happen with no indication at all, because the merge dropped every component
 * that read the mode store.
 */
export function ModeChips({ t }: { t: Theme }) {
  const { mode } = readMuseAgentMode()

  const chip = (id: string, label: string) => (
    <Text bold={mode === id} color={mode === id ? t.color.primary : t.color.faint} key={id}>
      {mode === id ? '● ' : '  '}
      {label}
    </Text>
  )

  return (
    <Text wrap="truncate-end">
      {chip('solo', 'Solo')}
      {chip('moa', 'MOA')}
      {chip('fusion', 'Fusion')}
      <Text color={t.color.faint}>{'   tab to switch'}</Text>
    </Text>
  )
}

/** Renders the sidebar only when the terminal is wide enough for it. */
export function CockpitSidebarSlot() {
  const visible = useSidebarVisible()
  const ui = $uiState.get()

  if (!visible) {
    return null
  }

  return <CockpitSidebar t={ui.theme} />
}
