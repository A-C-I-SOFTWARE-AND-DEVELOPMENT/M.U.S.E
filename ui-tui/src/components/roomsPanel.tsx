import { Box, Text, useInput, useStdout } from '@hermes/ink'
import { type ReactNode, useEffect, useState } from 'react'

import type { GatewayClient } from '../gatewayClient.js'
import { rpcErrorMessage } from '../lib/rpc.js'
import type { Theme } from '../theme.js'

import { OverlayHint, useOverlayKeys, windowItems } from './overlayControls.js'
import { chipRowProps, clampOverlayWidth } from './overlayPrimitives.js'
import { TextInput } from './textInput.js'

const VISIBLE = 10
const MIN_WIDTH = 44
const MAX_WIDTH = 96

/** The part of hermes_cli/rooms_db.py's wire shape this panel reads. */
interface RoomRow {
  id: string
  memberIds?: string[]
  name: string
}

interface RoomsListResponse {
  rooms?: RoomRow[]
}

interface RoomWriteResponse {
  room?: null | RoomRow
}

/**
 * The roster is edited as one comma-separated line rather than a sub-picker:
 * member ids are opaque to the store (see rooms_db.py's module docstring), so
 * there is no roster to pick FROM — only a list to type. The store strips,
 * de-duplicates and orders what arrives, so this side only has to split.
 */
const parseMembers = (raw: string): string[] =>
  raw
    .split(',')
    .map(part => part.trim())
    .filter(Boolean)

const formatMembers = (members: string[] | undefined): string => (members ?? []).join(', ')

type Mode = 'confirmDelete' | 'edit' | 'list'

type EditField = 'members' | 'name'

export function RoomsPanel({ gw, maxWidth, onClose, t }: RoomsPanelProps) {
  const [rows, setRows] = useState<RoomRow[]>([])
  const [idx, setIdx] = useState(0)
  const [err, setErr] = useState('')
  /**
   * Kept apart from `err` on purpose: the only notice this panel raises
   * outlives a reload, and `load()` clears `err` on success — so parking it
   * in `err` would erase the message with the very refresh that proves it.
   */
  const [notice, setNotice] = useState('')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)

  const [mode, setMode] = useState<Mode>('list')
  // null while creating; a room id while editing an existing one.
  const [editId, setEditId] = useState<null | string>(null)
  const [editField, setEditField] = useState<EditField>('name')
  const [draftName, setDraftName] = useState('')
  const [draftMembers, setDraftMembers] = useState('')

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

  const clampedIdx = Math.min(idx, Math.max(0, rows.length - 1))
  const selected = rows[clampedIdx]

  // `q` closes and Esc closes — correct in the list, wrong the moment a
  // TextInput is up, where `q` is a character the user may want to type and
  // Esc should only back out of the form.
  useOverlayKeys({ disabled: busy || mode !== 'list', onClose })

  const backToList = () => {
    setMode('list')
    setEditId(null)
    setErr('')
    setNotice('')
  }

  const openEditor = (room: null | RoomRow) => {
    setEditId(room?.id ?? null)
    setDraftName(room?.name ?? '')
    setDraftMembers(formatMembers(room?.memberIds))
    setEditField('name')
    setErr('')
    setNotice('')
    setMode('edit')
  }

  /**
   * Create or patch, then re-list so ordering comes from the store.
   *
   * Takes the field values as ARGUMENTS rather than reading `draftMembers` /
   * `draftName` off state, because on the Return keypath they can disagree.
   * `TextInput` hands `onSubmit` the value from `valueForReturnSubmit()`, which
   * folds in printable text that arrived in the SAME event as the Return — an
   * IME commit ("会議室\r") or a bracketed paste — text `onChange` was never
   * called for. `textInputSubmitClear.test.tsx` pins that contract upstream.
   * Reading state here would drop the last-typed characters, and for a name
   * typed entirely in one IME commit it would report "name required" about a
   * field the user can see is full.
   */
  const save = (membersRaw: string = draftMembers, nameRaw: string = draftName) => {
    const name = nameRaw.trim()

    if (!name) {
      // Checked here as well as server-side so the user hears about the one
      // required field without paying for a round trip.
      setErr('name required')
      setEditField('name')

      return
    }

    const params = { memberIds: parseMembers(membersRaw), name }
    const editing = editId

    setBusy(true)

    const write = editing
      ? gw.request<RoomWriteResponse>('rooms.update', { ...params, id: editing })
      : gw.request<RoomWriteResponse>('rooms.create', params)

    write
      .then(r => {
        backToList()

        // A null room from rooms.update means the row was deleted underneath
        // this panel. Saying so beats a silent no-op that looks like a save.
        if (editing && r?.room == null) {
          setNotice('that room no longer exists — nothing was saved')
        }

        load()
      })
      .catch((e: unknown) => setErr(rpcErrorMessage(e)))
      .finally(() => setBusy(false))
  }

  const remove = (room: RoomRow) => {
    setBusy(true)
    gw.request<{ deleted?: boolean }>('rooms.delete', { id: room.id })
      .then(() => {
        backToList()
        load()
      })
      .catch((e: unknown) => setErr(rpcErrorMessage(e)))
      .finally(() => setBusy(false))
  }

  useInput((ch, key) => {
    if (busy) {
      return
    }

    if (mode === 'edit') {
      if (key.escape) {
        return backToList()
      }

      // Tab moves between the two fields; Enter is the TextInput's own submit
      // (advance from name, save from members). Every other keystroke belongs
      // to the focused input — Tab is safe to steal because it is outside the
      // input's printable range and never reaches the value.
      if (key.tab) {
        return setEditField(f => (f === 'name' ? 'members' : 'name'))
      }

      return
    }

    if (mode === 'confirmDelete') {
      if (key.escape || ch === 'n') {
        return backToList()
      }

      if ((ch === 'y' || key.return) && selected) {
        remove(selected)
      }

      return
    }

    if (ch === 'n') {
      return openEditor(null)
    }

    if (ch === 'r') {
      setLoading(true)

      return load()
    }

    if (!rows.length) {
      return
    }

    if (key.downArrow || ch === 'j') {
      setIdx(i => Math.min(rows.length - 1, i + 1))
    }

    if (key.upArrow || ch === 'k') {
      setIdx(i => Math.max(0, i - 1))
    }

    if ((key.return || ch === 'e') && selected) {
      openEditor(selected)
    }

    if (ch === 'd' && selected) {
      setMode('confirmDelete')
    }
  })

  const frame = (children: ReactNode) => (
    <Box borderColor={t.color.border} borderStyle="round" flexDirection="column" paddingX={1} width={width}>
      <Text bold color={t.color.primary}>
        Rooms
        <Text color={t.color.muted}>{rows.length ? `  ${rows.length}` : ''}</Text>
      </Text>
      <Text color={t.color.muted}>Named rosters, kept per profile.</Text>
      <Text />
      {err ? <Text color={t.color.error}>{err}</Text> : null}
      {notice ? <Text color={t.color.label}>{notice}</Text> : null}
      {children}
    </Box>
  )

  if (mode === 'edit') {
    const fieldColumns = Math.max(8, width - 14)

    return frame(
      <>
        <Text color={t.color.muted}>{editId ? 'Edit room' : 'New room'}</Text>
        <Text />
        <Box>
          <Text color={editField === 'name' ? t.color.label : t.color.muted}>{'name    › '}</Text>
          <TextInput
            color={t.color.text}
            columns={fieldColumns}
            focus={editField === 'name'}
            onChange={setDraftName}
            onSubmit={submitted => {
              // The submitted value, not `draftName` — see `save`'s note on
              // same-event IME/paste text that never reached `onChange`.
              setDraftName(submitted)
              setEditField('members')
            }}
            placeholder="release crew"
            value={draftName}
          />
        </Box>
        <Box>
          <Text color={editField === 'members' ? t.color.label : t.color.muted}>{'members › '}</Text>
          <TextInput
            color={t.color.text}
            columns={fieldColumns}
            focus={editField === 'members'}
            onChange={setDraftMembers}
            onSubmit={submitted => save(submitted)}
            placeholder="comma, separated, ids"
            value={draftMembers}
          />
        </Box>
        <Text />
        <OverlayHint t={t}>{busy ? 'saving…' : 'Tab next field · Enter on members saves · Esc cancel'}</OverlayHint>
      </>
    )
  }

  if (mode === 'confirmDelete' && selected) {
    return frame(
      <>
        <Text color={t.color.text} wrap="truncate-end">
          Delete <Text bold>{selected.name}</Text>?
        </Text>
        <Text color={t.color.muted}>Its roster goes with it. This is not undoable.</Text>
        <Text />
        <OverlayHint t={t}>{busy ? 'deleting…' : 'y/Enter delete · n/Esc keep it'}</OverlayHint>
      </>
    )
  }

  if (loading) {
    return frame(
      <>
        <Text color={t.color.muted}>loading rooms…</Text>
        <OverlayHint t={t}>Esc/q close</OverlayHint>
      </>
    )
  }

  if (!rows.length) {
    return frame(
      <>
        {/* An empty store is the normal first-run state — nothing is seeded —
            so the empty message has to carry the way out of it. Suppressed
            when the list FAILED: "no rooms yet" would be a lie about an error. */}
        {err ? null : <Text color={t.color.muted}>No rooms yet.</Text>}
        <Text />
        <OverlayHint t={t}>n new room · r refresh · Esc/q close</OverlayHint>
      </>
    )
  }

  const { items: shown, offset } = windowItems(rows, clampedIdx, VISIBLE)

  return frame(
    <>
      {offset > 0 ? <Text color={t.color.muted}> ↑ {offset} more</Text> : null}

      {shown.map((room, i) => {
        const active = offset + i === clampedIdx
        const members = room.memberIds?.length ?? 0

        return (
          <Text key={room.id} {...chipRowProps(t, active)} wrap="truncate-end">
            {active ? '❯ ' : '  '}
            {room.name}
            <Text color={active ? undefined : t.color.muted}>
              {'  '}
              {members} {members === 1 ? 'member' : 'members'}
            </Text>
          </Text>
        )
      })}

      {offset + VISIBLE < rows.length ? (
        <Text color={t.color.muted}> ↓ {rows.length - offset - VISIBLE} more</Text>
      ) : null}

      {selected ? (
        <>
          <Text />
          <Text color={t.color.muted} wrap="truncate-end">
            {formatMembers(selected.memberIds) || 'no members yet — e to add some'}
          </Text>
        </>
      ) : null}

      <Text />
      <OverlayHint t={t}>↑↓/jk move · Enter/e edit · n new · d delete · r refresh · Esc/q close</OverlayHint>
    </>
  )
}

interface RoomsPanelProps {
  gw: GatewayClient
  maxWidth?: number
  onClose: () => void
  t: Theme
}
