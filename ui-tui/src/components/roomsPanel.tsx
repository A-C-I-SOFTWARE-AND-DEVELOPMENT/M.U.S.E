import { Box, Text, useInput, useStdout } from '@hermes/ink'
import { useEffect, useState } from 'react'

import type { GatewayClient } from '../gatewayClient.js'
import { rpcErrorMessage } from '../lib/rpc.js'
import type { Theme } from '../theme.js'

import { OverlayHint, useOverlayKeys, windowItems } from './overlayControls.js'
import { clampOverlayWidth } from './overlayPrimitives.js'

const VISIBLE = 12
const MIN_WIDTH = 44
const MAX_WIDTH = 96

/** Mirrors hermes_cli/rooms_db.py's wire shape (see Room.to_dict). */
interface RoomRow {
  createdAt?: number
  id: string
  memberIds?: string[]
  mixture?: string
  name: string
  preset?: boolean
  updatedAt?: number
}

interface RoomsListResponse {
  rooms?: RoomRow[]
}

/** How the room works the problem — the store's three mixtures. */
const MIXTURE_BLURB: Record<string, string> = {
  agents: 'everyone takes a turn, then one answer',
  council: 'the room talks it through, then one decides',
  experts: 'a few specialists take the parts they own'
}

const MIXTURE_GLYPH: Record<string, string> = {
  agents: '◆',
  council: '◉',
  experts: '◈'
}

export function RoomsPanel({ gw, maxWidth, onClose, t }: RoomsPanelProps) {
  const [rows, setRows] = useState<RoomRow[]>([])
  const [idx, setIdx] = useState(0)
  const [err, setErr] = useState('')
  const [loading, setLoading] = useState(true)

  const { stdout } = useStdout()
  const preferredWidth = Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, (stdout?.columns ?? 80) - 6))
  const width = clampOverlayWidth(preferredWidth, maxWidth)

  const load = () => {
    gw.request<RoomsListResponse>('rooms.list', {})
      .then(r => {
        setRows(r?.rooms ?? [])
        setErr('')
        setLoading(false)
      })
      .catch((e: unknown) => {
        setErr(rpcErrorMessage(e))
        setLoading(false)
      })
  }

  useEffect(load, [gw])

  useOverlayKeys({ onClose })

  const clampedIdx = Math.min(idx, Math.max(0, rows.length - 1))

  useInput((ch, key) => {
    const count = rows.length

    if (!count) {
      return
    }

    if (key.downArrow || ch === 'j') {
      setIdx(i => Math.min(count - 1, i + 1))
    }

    if (key.upArrow || ch === 'k') {
      setIdx(i => Math.max(0, i - 1))
    }

    if (ch === 'r') {
      setLoading(true)
      load()
    }
  })

  const { items: shown, offset } = windowItems(rows, clampedIdx, VISIBLE)
  const selected = rows[clampedIdx]

  const body = () => {
    if (loading) {
      return <Text color={t.color.muted}>loading rooms…</Text>
    }

    if (err) {
      return <Text color={t.color.error}>{err}</Text>
    }

    if (!rows.length) {
      // Honest empty state: the store seeds presets on first open, so an
      // empty list means the user deleted them all — not that rooms are
      // broken. Say which, so nobody goes looking for a bug.
      return <Text color={t.color.muted}>No rooms. Every preset was deleted; they are not re-seeded.</Text>
    }

    return (
      <>
        {shown.map((room, i) => {
          const active = offset + i === clampedIdx
          const mixture = (room.mixture ?? 'council').toLowerCase()
          const members = room.memberIds?.length ?? 0

          return (
            <Text key={room.id} wrap="truncate-end">
              <Text color={active ? t.color.primary : t.color.muted}>{active ? '❯ ' : '  '}</Text>
              <Text color={t.color.accent}>{MIXTURE_GLYPH[mixture] ?? '◉'} </Text>
              <Text bold={active} color={active ? t.color.primary : t.color.text}>
                {room.name}
              </Text>
              <Text color={t.color.faint}>
                {'  '}
                {members} {members === 1 ? 'member' : 'members'}
              </Text>
              {room.preset ? <Text color={t.color.faint}> · preset</Text> : null}
            </Text>
          )
        })}
      </>
    )
  }

  return (
    <Box borderColor={t.color.border} borderStyle="round" flexDirection="column" paddingX={1} width={width}>
      <Text bold color={t.color.primary}>
        Rooms
        <Text color={t.color.muted}>
          {'  '}
          {rows.length ? `${rows.length}` : ''}
        </Text>
      </Text>
      <Text color={t.color.muted}>Talk to one person, or ask a room.</Text>
      <Text />

      {body()}

      {selected ? (
        <>
          <Text />
          <Text color={t.color.faint} wrap="truncate-end">
            {MIXTURE_BLURB[(selected.mixture ?? 'council').toLowerCase()] ?? ''}
          </Text>
          <Text color={t.color.muted} wrap="truncate-end">
            {(selected.memberIds ?? []).join(' · ')}
          </Text>
        </>
      ) : null}

      <Text />
      <OverlayHint t={t}>↑↓/jk move · r refresh · esc close</OverlayHint>
    </Box>
  )
}

interface RoomsPanelProps {
  gw: GatewayClient
  maxWidth?: number
  onClose: () => void
  t: Theme
}
