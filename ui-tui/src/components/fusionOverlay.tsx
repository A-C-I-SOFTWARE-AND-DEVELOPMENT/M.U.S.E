import { Box, NoSelect, ScrollBox, type ScrollBoxHandle, Text, useInput } from '@hermes/ink'
import { type ReactNode, useCallback, useEffect, useRef, useState } from 'react'

import { applyFusionAvailability } from '../app/agentModeStore.js'
import type { GatewayClient } from '../gatewayClient.js'
import type {
  FusionDepth,
  FusionMoaStatus,
  FusionProgressPayload,
  FusionSetParams,
  FusionStatus
} from '../gatewayTypes.js'
import { rpcErrorMessage } from '../lib/rpc.js'
import type { Theme } from '../theme.js'

import { OverlayHint, useOverlayKeys } from './overlayControls.js'

// RPC types hoisted to gatewayTypes.ts by the Wave-3 integrator (see
// wiring/fusion.manifest.md §6); re-exported here for back-compat with the
// manifest's original import surface.
export type {
  FusionDepth,
  FusionModelRouterEntry,
  FusionMoaStatus,
  FusionProgressPayload,
  FusionSetParams,
  FusionStatus
} from '../gatewayTypes.js'

// ── Constants + helpers ──────────────────────────────────────────────

const DEPTH_CYCLE: readonly FusionDepth[] = ['skip', 'light', 'standard', 'deep', 'adaptive']
const MAX_ROUNDS = 5
const MAX_RUN_EVENTS = 24
const BAR_WIDTH = 10
const BAR_CHARS = ' ▁▂▃▄▅▆▇█'

const SECTIONS = [
  { key: 'status', title: 'Status' },
  { key: 'router', title: 'Model Router' },
  { key: 'moa', title: 'MOA' },
  { key: 'controls', title: 'Controls' },
  { key: 'lastrun', title: 'Last Run' }
] as const

type SectionKey = (typeof SECTIONS)[number]['key']

/** DOMElement type without importing the non-exported ink internal. */
type InkElement = Parameters<ScrollBoxHandle['scrollToElement']>[0]

interface FusionRunEvent {
  model?: string
  phase: string
  role?: string
  round?: number
  rounds?: number
}

/** EMA bias (0..1) → ascii block bar `▁▃▅▇` (design.md 1.3B §2). */
const biasBar = (bias: number, width = BAR_WIDTH) => {
  const v = Math.max(0, Math.min(1, Number.isFinite(bias) ? bias : 0))
  let out = ''

  for (let i = 0; i < width; i++) {
    const cell = Math.max(0, Math.min(1, v * width - i))

    out += BAR_CHARS[Math.round(cell * 8)]
  }

  return out
}

const roleColor = (t: Theme, role?: string) => {
  switch ((role ?? '').toUpperCase()) {
    case 'DIVERSE':
      return t.color.accent

    case 'SYNTHESIZE':
      return t.color.info ?? t.color.primary

    case 'VERIFY':
      return t.color.warn

    case 'POLISH':
      return t.color.ok

    default:
      return t.color.text
  }
}

const fmtAlpha = (a?: number) => (typeof a === 'number' && Number.isFinite(a) ? a.toFixed(3) : '—')

// ── Main overlay ─────────────────────────────────────────────────────

export function FusionOverlay({ gw, onClose, t }: FusionOverlayProps) {
  const [status, setStatus] = useState<FusionStatus | null>(null)
  const [gatewayErr, setGatewayErr] = useState('')
  const [busy, setBusy] = useState(false)
  const [flash, setFlash] = useState('')
  const [runEvents, setRunEvents] = useState<FusionRunEvent[]>([])

  const scrollRef = useRef<null | ScrollBoxHandle>(null)
  const sectionRefs = useRef<Partial<Record<SectionKey, InkElement | null>>>({})

  // ── Data ─────────────────────────────────────────────────────────

  const refresh = useCallback(() => {
    gw.request<FusionStatus>('fusion.status', {})
      .then(r => {
        const s = r ?? {}

        setStatus(s)
        setGatewayErr('')
        applyFusionAvailability(s)
      })
      .catch((e: unknown) => setGatewayErr(rpcErrorMessage(e)))
  }, [gw])

  useEffect(() => refresh(), [refresh])

  // Live fused-turn events (old gateways simply never emit these).
  useEffect(() => {
    const onEvent = (ev: unknown) => {
      const e = ev as { payload?: FusionProgressPayload & { done?: boolean; status?: string }; type?: string } | null

      if (!e || e.type !== 'fusion.progress') {
        return
      }

      const p = e.payload ?? {}
      const rawPhase = p.phase ?? p.status
      const phase = typeof rawPhase === 'string' && rawPhase ? rawPhase : p.done === true ? 'done' : 'start'

      setRunEvents(prev =>
        [...prev, { model: p.model, phase, role: p.role, round: p.round, rounds: p.rounds }].slice(-MAX_RUN_EVENTS)
      )
      refresh()
    }

    gw.on('event', onEvent)

    return () => {
      gw.off('event', onEvent)
    }
  }, [gw, refresh])

  // ── Controls (each: fusion.set → refetch via response) ───────────

  const send = (params: FusionSetParams, label: string) => {
    if (busy) {
      return
    }

    setBusy(true)
    setFlash('')

    gw.request<FusionStatus>('fusion.set', { ...params })
      .then(r => {
        const s = r ?? {}

        setStatus(s)
        setGatewayErr('')
        applyFusionAvailability(s)
        setFlash(label)
      })
      .catch((e: unknown) => setGatewayErr(rpcErrorMessage(e)))
      .finally(() => setBusy(false))
  }

  const cycleDepth = () => {
    const cur = (status?.depth ?? 'adaptive').toLowerCase() as FusionDepth
    const idx = DEPTH_CYCLE.indexOf(cur)
    const next = DEPTH_CYCLE[(idx + 1) % DEPTH_CYCLE.length] ?? 'skip'

    send({ depth: next }, `depth → ${next.toUpperCase()}`)
  }

  const cycleRounds = () => {
    const cur = Number(status?.rounds_planned ?? 1)
    const next = !Number.isFinite(cur) || cur >= MAX_ROUNDS ? 1 : Math.max(1, cur) + 1

    send({ rounds_cap: next }, `rounds cap → ${next}`)
  }

  const jumpTo = (key: SectionKey) => {
    const el = sectionRefs.current[key]

    if (el) {
      scrollRef.current?.scrollToElement(el)
    }
  }

  // ── Keys ─────────────────────────────────────────────────────────

  useOverlayKeys({ disabled: busy, onClose })

  useInput((ch, key) => {
    if (busy) {
      return
    }

    if (key.upArrow || ch === 'k') {
      return scrollRef.current?.scrollBy(-1)
    }

    if (key.downArrow || ch === 'j') {
      return scrollRef.current?.scrollBy(1)
    }

    if (ch === 'g') {
      return scrollRef.current?.scrollTo(0)
    }

    if (ch === 'G') {
      return scrollRef.current?.scrollToBottom()
    }

    const n = parseInt(ch, 10)

    if (n >= 1 && n <= SECTIONS.length) {
      return jumpTo(SECTIONS[n - 1]!.key)
    }

    const c = ch.toLowerCase()

    if (c === 'd') {
      return cycleDepth()
    }

    if (c === 'r') {
      return cycleRounds()
    }

    if (c === 'f') {
      const next = !status?.enabled

      return send({ enabled: next }, next ? 'fusion on' : 'fusion off')
    }

    if (c === 'm') {
      const next = !status?.moa?.enabled

      return send({ moa: next }, next ? 'moa on' : 'moa off')
    }
  })

  // ── Render ───────────────────────────────────────────────────────

  const moa = status?.moa ?? {}
  const router = status?.model_router ?? []
  const unavailable = Boolean(gatewayErr) || status?.available === false

  const Section = ({ id, n, title, children }: SectionProps) => (
    <Box
      flexDirection="column"
      marginTop={1}
      ref={(el: InkElement | null) => {
        sectionRefs.current[id] = el
      }}
    >
      <Text bold color={t.color.accent}>
        {n} · {title}
      </Text>
      {children}
    </Box>
  )

  return (
    <NoSelect>
      <Box flexDirection="column" flexGrow={1} paddingX={1}>
        <Box justifyContent="space-between">
          <Text bold color={t.color.accent}>
            ◈ Fusion / MOA center
          </Text>
          <Text color={t.color.muted}>{busy ? 'applying…' : flash}</Text>
        </Box>

        {unavailable && (
          <Box marginTop={1}>
            <Text color={t.color.warn}>
              ▲ fusion.status unreachable — requires newer gateway{gatewayErr ? ` (${gatewayErr})` : ''}
            </Text>
          </Box>
        )}

        <ScrollBox flexDirection="column" flexGrow={1} flexShrink={1} ref={scrollRef}>
          <Section id="status" n={1} title="Status">
            <Text>
              <Text color={(status?.enabled ?? false) ? t.color.ok : t.color.error}>
                {(status?.enabled ?? false) ? '✓ enabled' : '✖ disabled'}
              </Text>
              <Text color={t.color.text}>{'  depth '}</Text>
              <Text color={t.color.info ?? t.color.primary}>{(status?.depth ?? '—').toUpperCase()}</Text>
              <Text color={t.color.text}>{'  rounds '}</Text>
              <Text color={t.color.text}>
                {status?.current_round ?? 0}/{status?.rounds_planned ?? '—'}
              </Text>
            </Text>
            <Text>
              <Text color={t.color.text}>{'role '}</Text>
              <Text color={roleColor(t, status?.role)}>{(status?.role ?? '—').toUpperCase()}</Text>
              <Text color={t.color.text}>{'  lti α '}</Text>
              <Text color={t.color.text}>{fmtAlpha(status?.lti_alpha)}</Text>
            </Text>
          </Section>

          <Section id="router" n={2} title="Model Router">
            {router.length === 0 ? (
              <Text color={t.color.faint ?? t.color.muted}>no router data</Text>
            ) : (
              router.slice(0, 7).map((m, i) => (
                <Text key={`${m.model ?? 'model'}-${i}`}>
                  <Text color={t.color.text}>{(m.model ?? '?').padEnd(28).slice(0, 28)} </Text>
                  <Text color={t.color.muted}>{(m.specialty ?? '').padEnd(14).slice(0, 14)} </Text>
                  <Text color={t.color.accent}>{biasBar(Number(m.ema_bias ?? 0))}</Text>
                  <Text color={t.color.muted}>{` ${Number(m.ema_bias ?? 0).toFixed(2)} · ${m.calls ?? 0} calls`}</Text>
                </Text>
              ))
            )}
          </Section>

          <Section id="moa" n={3} title="MOA">
            <Text>
              <Text color={t.color.text}>{'mixture_of_agents tool  '}</Text>
              <Text color={(moa.enabled ?? false) ? t.color.ok : t.color.muted}>
                {(moa.enabled ?? false) ? '✓ on' : 'off (default)'}
              </Text>
            </Text>
            <Text>
              <Text color={t.color.text}>{'OPENROUTER_API_KEY      '}</Text>
              <Text color={(moa.key_present ?? false) ? t.color.ok : t.color.error}>
                {(moa.key_present ?? false) ? '✓ present' : '✖ missing'}
              </Text>
            </Text>
            <Text color={t.color.faint ?? t.color.muted}>press m to toggle</Text>
          </Section>

          <Section id="controls" n={4} title="Controls">
            <Text color={t.color.text}>
              <Text color={t.color.accent}>d</Text>
              {' cycle depth  (skip → light → standard → deep → adaptive)'}
            </Text>
            <Text color={t.color.text}>
              <Text color={t.color.accent}>r</Text>
              {` cycle rounds cap 1-${MAX_ROUNDS}  (now ${status?.rounds_planned ?? '—'})`}
            </Text>
            <Text color={t.color.text}>
              <Text color={t.color.accent}>f</Text>
              {` toggle fusion  (now ${(status?.enabled ?? false) ? 'on' : 'off'})`}
            </Text>
            <Text color={t.color.text}>
              <Text color={t.color.accent}>m</Text>
              {` toggle MOA  (now ${(moa.enabled ?? false) ? 'on' : 'off'})`}
            </Text>
          </Section>

          <Section id="lastrun" n={5} title="Last Run">
            {runEvents.length === 0 ? (
              <Text color={t.color.faint ?? t.color.muted}>no fused turns observed this session</Text>
            ) : (
              runEvents.map((e, i) => (
                <Text key={i}>
                  <Text color={t.color.accent}>{'◈ '}</Text>
                  <Text color={t.color.text}>{`round ${e.round ?? '?'}/${e.rounds ?? '?'} `}</Text>
                  <Text color={roleColor(t, e.role)}>{(e.role ?? '—').toUpperCase()}</Text>
                  <Text color={t.color.muted}>{` ${e.model ?? ''} · ${e.phase}`}</Text>
                </Text>
              ))
            )}
          </Section>
        </ScrollBox>

        <OverlayHint t={t}>1-5 section · j/k/↑↓ scroll · g/G top/bottom · d depth · r rounds · f fusion · m moa · q/Esc close</OverlayHint>
      </Box>
    </NoSelect>
  )
}

interface FusionOverlayProps {
  gw: GatewayClient
  onClose: () => void
  t: Theme
}

interface SectionProps {
  children: ReactNode
  id: SectionKey
  n: number
  title: string
}
