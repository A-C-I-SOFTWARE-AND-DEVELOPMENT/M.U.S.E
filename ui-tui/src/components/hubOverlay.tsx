import { Box, Text, useInput, useStdout } from '@hermes/ink'
import { useEffect, useMemo, useState } from 'react'

import { getDelegationState } from '../app/delegationStore.js'
import { useGateway } from '../app/gatewayContext.js'
import { getSpawnHistory } from '../app/spawnHistoryStore.js'
import type { ModelOptionsResponse } from '../gatewayTypes.js'
import { asRpcResult, rpcErrorMessage } from '../lib/rpc.js'
import type { Theme } from '../theme.js'

import { OverlayHint, windowItems } from './overlayControls.js'

// ── Hub browser (design.md §1.3C) ─────────────────────────────────────
//
// ONE overlay, left column = 5 hubs, right column = selected hub's rows.
// Every M.U.S.E. subsystem is reachable without tabs: ←/→ (h/l) switches
// hub, ↑/↓ (k/j) moves within content rows, Enter activates a row (most
// rows emit a slash command via onRunSlash), Esc closes.
//
// Live data is pulled best-effort from the new Wave-1 gateway RPCs
// (`cron.list`, `memory.status`) plus the existing `model.options`.  A
// rejected RPC or `{available: false}` renders a dim "requires newer
// gateway" hint — the overlay itself never crashes on old gateways.

const HUBS: HubDef[] = [
  { glyph: '◈', id: 'agents', name: 'Agents & Fusion' },
  { glyph: '◷', id: 'automation', name: 'Automation' },
  { glyph: '✦', id: 'skills', name: 'Skills & Tools' },
  { glyph: '▣', id: 'providers', name: 'Providers & Models' },
  { glyph: '●', id: 'memory', name: 'Memory & System' }
]

const LEFT_COL_WIDTH = 24
const MIN_WIDTH = 56
const NEW_GATEWAY_HINT = 'requires newer gateway'

type FetchState<T> = { data: null; error: string; status: 'unavailable' } | { data: null; error: null; status: 'loading' } | { data: T; error: null; status: 'ok' }

interface CronJob {
  enabled?: boolean
  id?: string
  last_run?: null | number | string
  last_status?: null | string
  name?: string
  next_run?: null | number | string
  schedule?: string
}

interface CronListResponse {
  available?: boolean
  error?: string
  jobs?: CronJob[]
}

interface HubDef {
  glyph: string
  id: HubId
  name: string
}

type HubId = 'agents' | 'automation' | 'memory' | 'providers' | 'skills'

interface HubOverlayProps {
  onClose: () => void
  onRunSlash: (cmd: string) => void
  t: Theme
}

interface HubRow {
  /** Slash command emitted via onRunSlash on Enter; absent = info row (dim, skipped by selection). */
  cmd?: string
  hint?: string
  key: string
  label: string
}

interface MemoryLayer {
  entries?: number
  last_write?: string
  name?: string
}

interface MemoryStatusResponse {
  available?: boolean
  layers?: MemoryLayer[]
}

const isSelectable = (row: HubRow) => Boolean(row.cmd)

const firstSelectable = (rows: HubRow[]) => {
  const idx = rows.findIndex(isSelectable)

  return idx === -1 ? 0 : idx
}

const stepSelection = (rows: HubRow[], sel: number, delta: -1 | 1) => {
  if (!rows.some(isSelectable)) {
    return sel
  }

  let next = sel

  for (let n = 0; n < rows.length; n += 1) {
    next = (next + delta + rows.length) % rows.length

    if (isSelectable(rows[next]!)) {
      return next
    }
  }

  return sel
}

const fmtWhen = (value: null | number | string | undefined): string => {
  if (value === null || value === undefined || value === '') {
    return '—'
  }

  if (typeof value === 'number' && Number.isFinite(value)) {
    const ms = value > 1e12 ? value : value * 1000
    const date = new Date(ms)

    return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString()
  }

  if (typeof value === 'string') {
    const date = new Date(value)

    return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
  }

  return String(value)
}

const infoRow = (key: string, label: string, hint?: string): HubRow => ({ key, label, ...(hint ? { hint } : {}) })

export function HubOverlay({ onClose, onRunSlash, t }: HubOverlayProps) {
  const { gw } = useGateway()
  const { stdout } = useStdout()

  const [hubIdx, setHubIdx] = useState(0)
  const [sel, setSel] = useState(0)
  const [cron, setCron] = useState<FetchState<CronListResponse>>({ data: null, error: null, status: 'loading' })
  const [memory, setMemory] = useState<FetchState<MemoryStatusResponse>>({ data: null, error: null, status: 'loading' })
  const [models, setModels] = useState<FetchState<ModelOptionsResponse>>({ data: null, error: null, status: 'loading' })

  // Best-effort parallel fetch; each RPC degrades independently so one
  // missing method never blanks the whole overlay.
  useEffect(() => {
    let alive = true

    gw.request<CronListResponse>('cron.list', {})
      .then(raw => {
        if (!alive) {
          return
        }

        const r = asRpcResult<CronListResponse>(raw)

        if (!r || r.available === false) {
          setCron({ data: null, error: r?.error ?? NEW_GATEWAY_HINT, status: 'unavailable' })

          return
        }

        setCron({ data: r, error: null, status: 'ok' })
      })
      .catch((e: unknown) => {
        if (alive) {
          setCron({ data: null, error: rpcErrorMessage(e), status: 'unavailable' })
        }
      })

    gw.request<MemoryStatusResponse>('memory.status', {})
      .then(raw => {
        if (!alive) {
          return
        }

        const r = asRpcResult<MemoryStatusResponse>(raw)

        if (!r) {
          setMemory({ data: null, error: NEW_GATEWAY_HINT, status: 'unavailable' })

          return
        }

        if (r.available === false && !(r.layers ?? []).length) {
          setMemory({ data: null, error: NEW_GATEWAY_HINT, status: 'unavailable' })

          return
        }

        setMemory({ data: r, error: null, status: 'ok' })
      })
      .catch((e: unknown) => {
        if (alive) {
          setMemory({ data: null, error: rpcErrorMessage(e), status: 'unavailable' })
        }
      })

    gw.request<ModelOptionsResponse>('model.options', {})
      .then(raw => {
        if (!alive) {
          return
        }

        const r = asRpcResult<ModelOptionsResponse>(raw)

        if (!r) {
          setModels({ data: null, error: 'invalid response: model.options', status: 'unavailable' })

          return
        }

        setModels({ data: r, error: null, status: 'ok' })
      })
      .catch((e: unknown) => {
        if (alive) {
          setModels({ data: null, error: rpcErrorMessage(e), status: 'unavailable' })
        }
      })

    return () => {
      alive = false
    }
  }, [gw])

  const rows = useMemo(() => buildRows(HUBS[hubIdx]!.id, { cron, memory, models }), [cron, hubIdx, memory, models])

  // Clamp the cursor when the row set shrinks underneath it (RPC landing,
  // hub switch) and never leave it parked on a non-selectable info row.
  const safeSel = rows.length ? Math.min(sel, rows.length - 1) : 0
  const cursor = isSelectable(rows[safeSel] ?? infoRow('none', '')) ? safeSel : firstSelectable(rows)

  const switchHub = (next: number) => {
    setHubIdx(next)
    setSel(0)
  }

  useInput((ch, key) => {
    if (ch === 'q' || key.escape) {
      return onClose()
    }

    if (key.leftArrow || ch === 'h') {
      return switchHub((hubIdx + HUBS.length - 1) % HUBS.length)
    }

    if (key.rightArrow || ch === 'l') {
      return switchHub((hubIdx + 1) % HUBS.length)
    }

    if (key.upArrow || ch === 'k') {
      return setSel(stepSelection(rows, cursor, -1))
    }

    if (key.downArrow || ch === 'j') {
      return setSel(stepSelection(rows, cursor, 1))
    }

    if (key.return) {
      const row = rows[cursor]

      if (row?.cmd) {
        // Close first so commands that open their own overlay (e.g.
        // /model, /agents) are not blocked by the hub.
        onClose()
        onRunSlash(row.cmd)
      }

      return
    }

    const n = parseInt(ch, 10)

    if (!Number.isNaN(n) && n >= 1 && n <= HUBS.length) {
      switchHub(n - 1)
    }
  })

  const cols = stdout?.columns ?? 80
  const rowsH = stdout?.rows ?? 24
  const width = Math.max(MIN_WIDTH, cols - 2)
  const visible = Math.max(5, rowsH - 9)
  const hub = HUBS[hubIdx]!
  const { items, offset } = windowItems(rows, cursor, visible)
  const faint = t.color.faint ?? t.color.muted

  return (
    <Box
      borderColor={t.color.accent}
      borderStyle="round"
      flexDirection="column"
      paddingX={1}
      width={width}
    >
      <Text bold color={t.color.accent}>
        M.U.S.E. Hub
      </Text>

      <Box flexDirection="row" marginTop={1}>
        <Box flexDirection="column" flexShrink={0} width={LEFT_COL_WIDTH}>
          {HUBS.map((h, i) => {
            const active = i === hubIdx

            return (
              <Text
                bold={active}
                color={active ? t.color.accent : t.color.muted}
                inverse={active}
                key={h.id}
                wrap="truncate-end"
              >
                {active ? '▸ ' : '  '}
                {h.glyph} {h.name}
              </Text>
            )
          })}
        </Box>

        <Box flexDirection="column" flexGrow={1} paddingLeft={1}>
          <Text bold color={t.color.text}>
            {hub.glyph} {hub.name}
          </Text>
          {offset > 0 && <Text color={faint}> ↑ {offset} more</Text>}

          {items.map((row, i) => {
            const idx = offset + i
            const active = idx === cursor && isSelectable(row)

            if (!isSelectable(row)) {
              return (
                <Text color={faint} key={row.key} wrap="truncate-end">
                  {'   '}
                  {row.label}
                  {row.hint ? ` · ${row.hint}` : ''}
                </Text>
              )
            }

            return (
              <Text
                bold={active}
                color={active ? t.color.accent : t.color.text}
                inverse={active}
                key={row.key}
                wrap="truncate-end"
              >
                {active ? ' ▸ ' : '   '}
                {row.label}
                {row.hint ? <Text color={active ? t.color.accent : faint}> · {row.hint}</Text> : null}
              </Text>
            )
          })}

          {offset + visible < rows.length && <Text color={faint}> ↓ {rows.length - offset - visible} more</Text>}
        </Box>
      </Box>

      <Box marginTop={1}>
        <OverlayHint t={t}>←/→ hub · ↑/↓ select · Enter run · 1-5 jump · Esc/q close</OverlayHint>
      </Box>
    </Box>
  )
}

// ── Row builders ──────────────────────────────────────────────────────

function buildRows(
  hub: HubId,
  data: {
    cron: FetchState<CronListResponse>
    memory: FetchState<MemoryStatusResponse>
    models: FetchState<ModelOptionsResponse>
  }
): HubRow[] {
  switch (hub) {
    case 'agents':
      return agentsRows()

    case 'automation':
      return automationRows(data.cron)

    case 'memory':
      return memoryRows(data.memory)

    case 'providers':
      return providerRows(data.models)

    case 'skills':
      return skillsRows()
  }
}

function agentsRows(): HubRow[] {
  const rows: HubRow[] = [
    { cmd: '/fusion', hint: 'fusion center · status, depth, router', key: 'fusion', label: '◈ Fusion center' },
    { cmd: '/agents', hint: 'live spawn-tree dashboard', key: 'agents', label: '⚙ Agents dashboard' },
    { cmd: '/replay', hint: 'replay last completed spawn tree', key: 'replay', label: '⟲ Replay spawn tree' }
  ]

  // Spawn-tree summary — cheap, read-only from existing stores.
  const delegation = getDelegationState()
  const history = getSpawnHistory()

  if (delegation.updatedAt !== null) {
    rows.push(
      infoRow(
        'delegation',
        `delegation · ${delegation.paused ? 'paused' : 'active'}`,
        `caps d${delegation.maxSpawnDepth ?? '?'}/${delegation.maxConcurrentChildren ?? '?'}`
      )
    )
  }

  if (history.length) {
    const latest = history[0]!
    const running = latest.subagents.filter(s => s.status === 'running' || s.status === 'queued').length

    rows.push(
      infoRow(
        'spawns',
        `spawn history · ${history.length} snapshot${history.length === 1 ? '' : 's'}`,
        `latest: ${latest.label}${running ? ` · ${running} live` : ''}`
      )
    )
  }

  return rows
}

function automationRows(cron: FetchState<CronListResponse>): HubRow[] {
  const rows: HubRow[] = []

  if (cron.status === 'loading') {
    rows.push(infoRow('loading', '◷ loading cron jobs…'))
  } else if (cron.status === 'unavailable') {
    rows.push(infoRow('unavailable', `◷ cron.list ${NEW_GATEWAY_HINT}`, cron.error || undefined))
  } else {
    const jobs = cron.data.jobs ?? []

    if (!jobs.length) {
      rows.push(infoRow('empty', 'no cron jobs scheduled'))
    }

    for (const [i, job] of jobs.entries()) {
      const id = job.id ?? ''
      const enabled = job.enabled !== false
      const status = job.last_status ? ` · last ${job.last_status}` : ''

      rows.push({
        cmd: id ? `/cron ${enabled ? 'pause' : 'resume'} ${id}` : '/cron list',
        hint: `${job.schedule || '—'} · next ${fmtWhen(job.next_run)}${status}`,
        key: `job-${id || i}`,
        label: `${enabled ? '●' : '○'} ${job.name || id || 'cron job'}`
      })
    }
  }

  rows.push(
    { cmd: '/cron list', hint: 'full cron listing via CLI passthrough', key: 'cron-list', label: '◷ Cron list' }
  )

  return rows
}

function skillsRows(): HubRow[] {
  return [
    { cmd: '/skills', hint: 'browse, inspect, install', key: 'skills', label: '✦ Skills hub' },
    { cmd: '/tools', hint: 'toolsets & tools · enable/disable', key: 'tools', label: '⏺ Tools' },
    { cmd: '/reload-skills', hint: 'reload skill registry', key: 'reload-skills', label: 'Reload skills' },
    { cmd: '/reload-mcp', hint: 'reload MCP servers', key: 'reload-mcp', label: 'Reload MCP' }
  ]
}

function providerRows(models: FetchState<ModelOptionsResponse>): HubRow[] {
  const rows: HubRow[] = [
    { cmd: '/model', hint: 'provider → model picker', key: 'model', label: '▣ Model picker' },
    { cmd: '/fast', hint: 'toggle fast mode', key: 'fast', label: 'Fast mode' },
    { cmd: '/reasoning', hint: 'cycle reasoning effort', key: 'reasoning', label: 'Reasoning effort' }
  ]

  if (models.status === 'loading') {
    rows.push(infoRow('loading', '▣ loading model options…'))

    return rows
  }

  if (models.status === 'unavailable') {
    rows.push(infoRow('unavailable', '▣ model.options unavailable', models.error || undefined))

    return rows
  }

  if (models.data.model) {
    rows.push(
      infoRow('current', `current · ${models.data.model}`, models.data.provider ? `via ${models.data.provider}` : undefined)
    )
  }

  for (const p of models.data.providers ?? []) {
    const count = p.total_models ?? p.models?.length
    const marks = [p.is_current ? 'current' : '', p.authenticated === false ? 'no key' : ''].filter(Boolean).join(' · ')

    rows.push(
      infoRow(
        `provider-${p.slug}`,
        `${p.authenticated === false ? '✖' : '✓'} ${p.name}`,
        [count ? `${count} models` : '', marks].filter(Boolean).join(' · ') || undefined
      )
    )
  }

  return rows
}

function memoryRows(memory: FetchState<MemoryStatusResponse>): HubRow[] {
  const rows: HubRow[] = [
    { cmd: '/logs', hint: 'tail gateway logs', key: 'logs', label: 'Logs' },
    { cmd: '/mem', hint: 'memory usage snapshot', key: 'mem', label: 'Memory usage' },
    { cmd: '/status', hint: 'session status', key: 'status', label: 'Status' },
    { cmd: '/usage', hint: 'token usage & cost', key: 'usage', label: 'Usage' },
    { cmd: '/details', hint: 'toggle tool-result expansion', key: 'details', label: 'Details mode' }
  ]

  if (memory.status === 'loading') {
    rows.push(infoRow('loading', '● loading memory layers…'))
  } else if (memory.status === 'unavailable') {
    rows.push(infoRow('unavailable', `● memory.status ${NEW_GATEWAY_HINT}`, memory.error || undefined))
  } else {
    const layers = memory.data.layers ?? []

    if (!layers.length) {
      rows.push(infoRow('empty', 'no memory layers recorded yet'))
    }

    for (const layer of layers) {
      rows.push(
        infoRow(
          `layer-${layer.name ?? '?'}`,
          `● ${layer.name ?? 'layer'}`,
          `${layer.entries ?? 0} entries · ${layer.last_write ?? '—'}`
        )
      )
    }
  }

  return rows
}
