import { Box, type ScrollBoxHandle, Text } from '@hermes/ink'
import { type ReactNode, type RefObject, useEffect, useMemo, useRef, useState } from 'react'

import { useTurnSelector } from '../app/turnStore.js'
import { VERBS } from '../content/verbs.js'
import { stickyPromptFromViewport } from '../domain/viewport.js'
import { buildSubagentTree, treeTotals } from '../lib/subagentTree.js'
import { fmtK } from '../lib/text.js'
import { useScrollbarSnapshot, useViewportSnapshot } from '../lib/viewportStore.js'
import type { Theme } from '../theme.js'
import type { Msg, Usage } from '../types.js'

// Keep verb segment width stable so status/spinner lines don't jitter when
// the ticker rotates between short/long verbs.  Shared with the busy spinner
// line (thinking.tsx) via these exports.
export const VERB_PAD_LEN = VERBS.reduce((max, v) => Math.max(max, v.length), 0) + 1 // + ellipsis
export const padVerb = (verb: string) => `${verb}…`.padEnd(VERB_PAD_LEN, ' ')

// ── Agent-mode contract ──────────────────────────────────────────────
//
// The Wave-3 integrator installs `globalThis.__museAgentMode = () => snap`
// (backed by Wave-2's `app/agentModeStore.ts`).  `snap` may be a plain mode
// string ('solo' | 'moa' | 'fusion') or a MuseAgentModeSnapshot object.
// Missing getter, bad payloads, and throws all degrade to solo/default.

export type MuseAgentMode = 'fusion' | 'moa' | 'solo'

export interface MuseAgentModeSnapshot {
  /** Active agent mode (case-insensitive): 'solo' | 'moa' | 'fusion'. */
  mode?: null | string
  /** Permission mode (case-insensitive), e.g. 'default' | 'plan' | 'yolo'. */
  permission?: null | string
  /** Capability flags for banner/status availability readouts. */
  fusionAvailable?: boolean
  moaAvailable?: boolean
}

export interface MuseAgentModeState {
  fusionAvailable?: boolean
  moaAvailable?: boolean
  mode: MuseAgentMode
  permission: string
}

export function readMuseAgentMode(): MuseAgentModeState {
  try {
    const getter = (globalThis as { __museAgentMode?: unknown }).__museAgentMode

    if (typeof getter !== 'function') {
      return { mode: 'solo', permission: '' }
    }

    const raw = (getter as () => unknown)()
    const snap: MuseAgentModeSnapshot =
      typeof raw === 'string' ? { mode: raw } : raw && typeof raw === 'object' ? (raw as MuseAgentModeSnapshot) : {}
    const mode = String(snap.mode ?? '')
      .trim()
      .toLowerCase()

    return {
      mode: mode === 'moa' || mode === 'fusion' ? mode : 'solo',
      permission: String(snap.permission ?? '')
        .trim()
        .toLowerCase(),
      moaAvailable: typeof snap.moaAvailable === 'boolean' ? snap.moaAvailable : undefined,
      fusionAvailable: typeof snap.fusionAvailable === 'boolean' ? snap.fusionAvailable : undefined
    }
  } catch {
    return { mode: 'solo', permission: '' }
  }
}

/** Status-bar badge per design.md 1.2: SOLO accentDim / MOA warn / ◈FUSION accent. */
export function agentModeBadge(mode: MuseAgentMode, t: Theme): { color: string; text: string } {
  if (mode === 'fusion') {
    return { text: '◈FUSION', color: t.color.accent }
  }

  if (mode === 'moa') {
    return { text: 'MOA', color: t.color.warn }
  }

  return { text: 'SOLO', color: t.color.accentDim ?? t.color.muted }
}

function ctxBarColor(pct: number | undefined, t: Theme) {
  if (pct == null) {
    return t.color.muted
  }

  if (pct >= 95) {
    return t.color.statusCritical
  }

  if (pct > 80) {
    return t.color.statusBad
  }

  if (pct >= 50) {
    return t.color.statusWarn
  }

  return t.color.statusGood
}

const effortLabel = (effort?: string) => {
  const value = String(effort ?? '')
    .trim()
    .toLowerCase()

  return value && value !== 'medium' && value !== 'normal' && value !== 'default' ? value : ''
}

const shortModelLabel = (model: string) =>
  model
    .split('/')
    .pop()!
    .replace(/^claude[-_]/, '')
    .replace(/^anthropic[-_]/, '')
    .replace(/[-_]/g, ' ')
    .replace(/\b(\d+)\s+(\d+)\b/g, '$1.$2')
    .trim()

const modelLabel = (model: string, effort?: string, fast?: boolean) =>
  [shortModelLabel(model), effortLabel(effort), fast ? 'fast' : ''].filter(Boolean).join(' ')

export function GoodVibesHeart({ tick, t }: { tick: number; t: Theme }) {
  const [active, setActive] = useState(false)
  const [color, setColor] = useState(t.color.accent)

  useEffect(() => {
    if (tick <= 0) {
      return
    }

    const palette = [t.color.error, t.color.warn, t.color.accent]
    setColor(palette[Math.floor(Math.random() * palette.length)]!)
    setActive(true)

    const id = setTimeout(() => setActive(false), 650)

    return () => clearTimeout(id)
  }, [t.color.accent, tick])

  if (!active) {
    return null
  }

  return <Text color={color}>♥</Text>
}

interface StatusItem {
  color: string
  key: string
  text: string
}

const SEP = ' · '

export function StatusRule({
  cwdLabel,
  cols,
  gitBranch,
  model,
  modelFast,
  modelReasoningEffort,
  usage,
  t
}: StatusRuleProps) {
  const subagents = useTurnSelector(state => state.subagents)
  const tree = useMemo(() => buildSubagentTree(subagents), [subagents])
  const totals = useMemo(() => treeTotals(tree), [tree])

  const pct = usage.context_percent
  const faint = t.color.faint ?? t.color.border
  const badge = agentModeBadge(readMuseAgentMode().mode, t)

  // Genre status bar (design.md 1.2), L→R:
  //   cwd · git-branch · model · mode badge · ⚙N · ctx% · tokens · ^P hint
  // cwd is leftmost and flexes; every other item drops rightmost-first
  // when the row would overflow `cols`.
  const items: StatusItem[] = []

  if (gitBranch) {
    items.push({ key: 'git', text: gitBranch, color: faint })
  }

  const modelText = model ? modelLabel(model, modelReasoningEffort, modelFast) : ''

  if (modelText) {
    items.push({ key: 'model', text: modelText, color: t.color.muted })
  }

  items.push({ key: 'mode', text: badge.text, color: badge.color })

  if (totals.activeCount > 0) {
    items.push({ key: 'agents', text: `⚙${totals.activeCount}`, color: t.color.muted })
  }

  if (pct != null) {
    items.push({ key: 'ctx', text: `${Math.round(pct)}% ctx`, color: ctxBarColor(pct, t) })
  }

  if (usage.total > 0) {
    items.push({ key: 'tokens', text: fmtK(usage.total), color: faint })
  }

  items.push({ key: 'hint', text: '^P palette', color: faint })

  const itemsWidth = (list: StatusItem[]) =>
    list.length ? list.reduce((n, i) => n + i.text.length, 0) + SEP.length * list.length : 0

  const fitted = [...items]

  while (fitted.length > 0 && cwdLabel.length + itemsWidth(fitted) > cols) {
    fitted.pop()
  }

  const cwdBudget = Math.max(1, cols - itemsWidth(fitted))
  const cwd = cwdLabel.length > cwdBudget ? `${cwdLabel.slice(0, Math.max(1, cwdBudget - 1))}…` : cwdLabel

  return (
    <Box height={1}>
      <Text wrap="truncate-end">
        <Text color={t.color.label}>{cwd}</Text>
        {fitted.map(item => (
          <Text key={item.key}>
            <Text color={faint}>{SEP}</Text>
            <Text color={item.color}>{item.text}</Text>
          </Text>
        ))}
      </Text>
    </Box>
  )
}

export function FloatBox({ children, color }: { children: ReactNode; color: string }) {
  return (
    <Box
      alignSelf="flex-start"
      borderColor={color}
      borderStyle="round"
      flexDirection="column"
      marginTop={1}
      opaque
      paddingX={1}
    >
      {children}
    </Box>
  )
}

export function StickyPromptTracker({ messages, offsets, scrollRef, onChange }: StickyPromptTrackerProps) {
  const { atBottom, bottom, top } = useViewportSnapshot(scrollRef)
  const text = stickyPromptFromViewport(messages, offsets, top, bottom, atBottom)

  useEffect(() => onChange(text), [onChange, text])

  return null
}

export function TranscriptScrollbar({ scrollRef, t }: TranscriptScrollbarProps) {
  const [hover, setHover] = useState(false)
  const [grab, setGrab] = useState<number | null>(null)
  const grabRef = useRef<number | null>(null)
  const { scrollHeight: total, top: pos, viewportHeight: vp } = useScrollbarSnapshot(scrollRef)

  if (!vp) {
    return <Box width={1} />
  }

  const s = scrollRef.current
  const scrollable = total > vp
  const thumb = scrollable ? Math.max(1, Math.round((vp * vp) / total)) : vp
  const travel = Math.max(1, vp - thumb)
  const thumbTop = scrollable ? Math.round((pos / Math.max(1, total - vp)) * travel) : 0
  const thumbColor = grab !== null ? t.color.primary : hover ? t.color.accent : t.color.border
  const trackColor = hover ? t.color.border : t.color.muted

  const jump = (row: number, offset: number) => {
    if (!s || !scrollable) {
      return
    }

    s.scrollTo(Math.round((Math.max(0, Math.min(travel, row - offset)) / travel) * Math.max(0, total - vp)))
  }

  return (
    <Box
      flexDirection="column"
      onMouseDown={(e: { localRow?: number }) => {
        const row = Math.max(0, Math.min(vp - 1, e.localRow ?? 0))
        const off = row >= thumbTop && row < thumbTop + thumb ? row - thumbTop : Math.floor(thumb / 2)

        grabRef.current = off
        setGrab(off)
        jump(row, off)
      }}
      onMouseDrag={(e: { localRow?: number }) =>
        jump(Math.max(0, Math.min(vp - 1, e.localRow ?? 0)), grabRef.current ?? Math.floor(thumb / 2))
      }
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      onMouseUp={() => {
        grabRef.current = null
        setGrab(null)
      }}
      width={1}
    >
      {!scrollable ? (
        <Text color={trackColor} dim>
          {' \n'.repeat(Math.max(0, vp - 1))}{' '}
        </Text>
      ) : (
        <>
          {thumbTop > 0 ? (
            <Text color={trackColor} dim={!hover}>
              {`${'│\n'.repeat(Math.max(0, thumbTop - 1))}${thumbTop > 0 ? '│' : ''}`}
            </Text>
          ) : null}
          {thumb > 0 ? (
            <Text color={thumbColor}>{`${'┃\n'.repeat(Math.max(0, thumb - 1))}${thumb > 0 ? '┃' : ''}`}</Text>
          ) : null}
          {vp - thumbTop - thumb > 0 ? (
            <Text color={trackColor} dim={!hover}>
              {`${'│\n'.repeat(Math.max(0, vp - thumbTop - thumb - 1))}${vp - thumbTop - thumb > 0 ? '│' : ''}`}
            </Text>
          ) : null}
        </>
      )}
    </Box>
  )
}

interface StatusRuleProps {
  bgCount: number
  busy: boolean
  cols: number
  cwdLabel: string
  /** Git branch (e.g. `main*`); rendered when the integrator wires it in. */
  gitBranch?: string
  model: string
  modelFast?: boolean
  modelReasoningEffort?: string
  sessionStartedAt?: null | number
  showCost: boolean
  status: string
  statusColor: string
  t: Theme
  turnStartedAt?: null | number
  usage: Usage
  voiceLabel?: string
}

interface StickyPromptTrackerProps {
  messages: readonly Msg[]
  offsets: ArrayLike<number>
  onChange: (text: string) => void
  scrollRef: RefObject<ScrollBoxHandle | null>
}

interface TranscriptScrollbarProps {
  scrollRef: RefObject<ScrollBoxHandle | null>
  t: Theme
}
