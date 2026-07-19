import { Box, useStdout } from '@hermes/ink'
import { useMemo } from 'react'

import { SLASH_COMMANDS } from '../app/slash/registry.js'
import type { Theme } from '../theme.js'

import { type FuzzyItem, FuzzyList } from './fuzzyList.js'

const FOOTER = '↑↓ navigate · ⏎ run · esc close'

// Categories mirror the five hubs (design.md 1.3A/1.3C): Agents · Automate ·
// Skills · Session · System. Promoted entries are hub shortcuts + common
// config toggles; every one emits its slash command verbatim.
interface PromotedEntry {
  category: string
  cmd: string
  hint: string
  keywords?: string
}

const PROMOTED: PromotedEntry[] = [
  // ── Agents ─────────────────────────────────────────────────────────
  { category: 'Agents', cmd: '/fusion', hint: 'fusion & MOA control center', keywords: 'moa mixture fuse router rounds depth' },
  { category: 'Agents', cmd: '/agents', hint: 'agents dashboard (full-screen)', keywords: 'subagents delegation gantt replay' },
  // ── Automate ───────────────────────────────────────────────────────
  { category: 'Automate', cmd: '/queue', hint: 'inspect or enqueue queued messages', keywords: 'busy steer pending' },
  // ── Skills ─────────────────────────────────────────────────────────
  { category: 'Skills', cmd: '/skills', hint: 'skills hub: browse, inspect, install', keywords: 'tools plugins manage' },
  // ── Session ────────────────────────────────────────────────────────
  { category: 'Session', cmd: '/model', hint: 'change or show model', keywords: 'provider picker switch' },
  { category: 'Session', cmd: '/sessions', hint: 'browse and resume previous sessions', keywords: 'resume picker history' },
  { category: 'Session', cmd: '/usage', hint: 'token usage for this session', keywords: 'tokens cost context' },
  { category: 'Session', cmd: '/status', hint: 'show live session info', keywords: 'state title model' },
  { category: 'Session', cmd: '/fast toggle', hint: 'toggle fast mode', keywords: 'speed normal quick' },
  { category: 'Session', cmd: '/yolo', hint: 'toggle yolo mode (auto-approve)', keywords: 'approvals permissions' },
  { category: 'Session', cmd: '/reasoning show', hint: 'show reasoning in transcript', keywords: 'thinking effort' },
  // ── System ─────────────────────────────────────────────────────────
  { category: 'System', cmd: '/hub', hint: 'open the hub browser', keywords: 'hubs agents automate skills providers memory' },
  { category: 'System', cmd: '/logs', hint: 'view gateway logs', keywords: 'debug tail trace' },
  { category: 'System', cmd: '/mem', hint: 'memory usage stats', keywords: 'heap debug' },
  { category: 'System', cmd: '/details', hint: 'control agent detail visibility', keywords: 'thinking tools sections collapsed' },
  { category: 'System', cmd: '/skin', hint: 'switch theme skin', keywords: 'theme colors appearance' },
  { category: 'System', cmd: '/theme', hint: 'switch theme (gateway alias)', keywords: 'skin colors appearance' },
  { category: 'System', cmd: '/help', hint: 'list commands + hotkeys', keywords: 'commands keys shortcuts' },
  { category: 'System', cmd: '/mouse', hint: 'toggle mouse/wheel tracking', keywords: 'scroll click tracking' },
  { category: 'System', cmd: '/compact', hint: 'toggle compact transcript', keywords: 'density spacing' },
  { category: 'System', cmd: '/statusbar', hint: 'cycle status bar position', keywords: 'top bottom off chrome' }
]

const buildPalette = () => {
  const items: FuzzyItem[] = []
  const commands = new Map<string, string>()
  // Primary command names already covered by a promoted entry — keeps one
  // row per command so fuzzy results never show duplicates.
  const promotedNames = new Set(PROMOTED.map(p => p.cmd.split(' ')[0]!.slice(1).toLowerCase()))

  for (const p of PROMOTED) {
    const id = `run:${p.cmd}`
    const name = p.cmd.split(' ')[0]!.slice(1)
    const reg = SLASH_COMMANDS.find(c => c.name === name || (c.aliases ?? []).includes(name))

    items.push({
      category: p.category,
      hint: p.hint,
      id,
      keywords: [p.keywords ?? '', reg?.help ?? '', ...(reg?.aliases ?? [])].filter(Boolean).join(' '),
      label: p.cmd
    })
    commands.set(id, p.cmd)
  }

  for (const cmd of SLASH_COMMANDS) {
    if (promotedNames.has(cmd.name)) {
      continue
    }

    const id = `cmd:${cmd.name}`

    items.push({
      category: 'Commands',
      hint: cmd.help,
      id,
      keywords: [...(cmd.aliases ?? []), cmd.usage ?? ''].filter(Boolean).join(' '),
      label: `/${cmd.name}`
    })
    commands.set(id, `/${cmd.name}`)
  }

  return { commands, items }
}

export function CommandPalette({ onClose, onRunSlash, t }: CommandPaletteProps) {
  const { stdout } = useStdout()
  // design.md 1.3A: float sized to ~60% of terminal width.
  const width = Math.max(44, Math.round((stdout?.columns ?? 80) * 0.6))

  const palette = useMemo(buildPalette, [])

  const pick = (item: FuzzyItem) => {
    const cmd = palette.commands.get(item.id)

    onClose()

    if (cmd) {
      onRunSlash(cmd)
    }
  }

  // Owns its rounded accent border — mount BARE inside FloatingOverlays
  // (wrapping in FloatBox would draw a second border).
  return (
    <Box
      borderColor={t.color.accent}
      borderStyle="round"
      flexDirection="column"
      marginTop={1}
      opaque
      paddingX={1}
      width={width}
    >
      <FuzzyList
        footer={FOOTER}
        items={palette.items}
        maxRows={12}
        onClose={onClose}
        onPick={pick}
        placeholder="type a command or search…"
        t={t}
      />
    </Box>
  )
}

interface CommandPaletteProps {
  t: Theme
  onClose: () => void
  onRunSlash: (cmd: string) => void
}
