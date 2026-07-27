import { Box, Text, useInput, useStdout } from '@hermes/ink'
import { useEffect, useState } from 'react'

import { THINKING_LEVELS, type ThinkingEffort } from '../domain/thinkingLevels.js'
import type { GatewayClient } from '../gatewayClient.js'
import type { ConfigGetValueResponse } from '../gatewayTypes.js'
import { asRpcResult, rpcErrorMessage } from '../lib/rpc.js'
import type { Theme } from '../theme.js'

import { OverlayHint, useOverlayKeys, windowItems } from './overlayControls.js'

const VISIBLE = 10
const MIN_WIDTH = 44
const MAX_WIDTH = 76

type DisplayAction = 'hide' | 'show'

interface Row {
  group: 'display' | 'effort'
  hint: string
  id: DisplayAction | ThinkingEffort
  label: string
}

const ROWS: Row[] = [
  ...THINKING_LEVELS.map(
    (l): Row => ({ group: 'effort', hint: l.hint, id: l.id, label: l.label })
  ),
  { group: 'display', hint: 'stream thinking into the transcript', id: 'show', label: 'Show thinking' },
  { group: 'display', hint: 'hide thinking shelves', id: 'hide', label: 'Hide thinking' }
]

export function ThinkingPicker({ gw, onCancel, onSelect, t }: ThinkingPickerProps) {
  const [current, setCurrent] = useState('')
  const [display, setDisplay] = useState<'hide' | 'show'>('hide')
  const [err, setErr] = useState('')
  const [idx, setIdx] = useState(0)
  const [loading, setLoading] = useState(true)

  const { stdout } = useStdout()
  const width = Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, (stdout?.columns ?? 80) - 6))

  useEffect(() => {
    gw.request<ConfigGetValueResponse>('config.get', { key: 'reasoning' })
      .then(raw => {
        const r = asRpcResult<ConfigGetValueResponse>(raw)

        if (!r) {
          setErr('invalid response: config.get reasoning')
          setLoading(false)

          return
        }

        const effort = String(r.value ?? 'medium')
          .trim()
          .toLowerCase()
        setCurrent(effort)
        setDisplay(r.display === 'show' ? 'show' : 'hide')
        const start = ROWS.findIndex(row => row.id === effort)
        setIdx(start >= 0 ? start : THINKING_LEVELS.findIndex(l => l.id === 'medium'))
        setErr('')
        setLoading(false)
      })
      .catch((e: unknown) => {
        setErr(rpcErrorMessage(e))
        setLoading(false)
      })
  }, [gw])

  useOverlayKeys({ onClose: onCancel })

  useInput((_ch, key) => {
    if (loading) {
      return
    }

    if (key.upArrow || key.downArrow) {
      setIdx(i => {
        const next = key.upArrow ? i - 1 : i + 1

        return (next + ROWS.length) % ROWS.length
      })

      return
    }

    if (key.return) {
      const row = ROWS[idx]

      if (row) {
        onSelect(row.id)
      }
    }
  })

  if (loading) {
    return (
      <Box flexDirection="column" width={width}>
        <Text bold color={t.color.accent}>
          Thinking level
        </Text>
        <Text color={t.color.muted}>loading…</Text>
      </Box>
    )
  }

  const { items, offset } = windowItems(ROWS, idx, VISIBLE)

  return (
    <Box flexDirection="column" width={width}>
      <Text bold color={t.color.accent} wrap="truncate-end">
        Thinking level
      </Text>
      <Text color={t.color.muted} wrap="truncate-end">
        current · {current || 'medium'} · transcript {display}
      </Text>
      {err ? (
        <Text color={t.color.error} wrap="truncate-end">
          {err}
        </Text>
      ) : (
        <Text color={t.color.muted} wrap="truncate-end">
          pick effort, or show/hide thinking in the transcript
        </Text>
      )}

      <Text color={t.color.muted} wrap="truncate-end">
        {offset > 0 ? ` ↑ ${offset} more` : ' '}
      </Text>

      {Array.from({ length: VISIBLE }, (_, i) => {
        const row = items[i]
        const absolute = offset + i

        if (!row) {
          return (
            <Text color={t.color.muted} key={`pad-${i}`} wrap="truncate-end">
              {' '}
            </Text>
          )
        }

        const active = idx === absolute
        const selected =
          (row.group === 'effort' && row.id === current) || (row.group === 'display' && row.id === display)
        const prefix = active ? '▸ ' : selected ? '* ' : '  '
        const tag = row.group === 'display' ? 'view' : 'think'

        return (
          <Text
            bold={active}
            color={active ? t.color.accent : t.color.muted}
            inverse={active}
            key={row.id}
            wrap="truncate-end"
          >
            {prefix}
            [{tag}] {row.label}
            <Text color={t.color.label}> — {row.hint}</Text>
          </Text>
        )
      })}

      <Text color={t.color.muted} wrap="truncate-end">
        {offset + VISIBLE < ROWS.length ? ` ↓ ${ROWS.length - offset - VISIBLE} more` : ' '}
      </Text>
      <OverlayHint t={t}>↑/↓ select · Enter apply · Esc/q cancel</OverlayHint>
    </Box>
  )
}

interface ThinkingPickerProps {
  gw: GatewayClient
  onCancel: () => void
  onSelect: (value: string) => void
  t: Theme
}
