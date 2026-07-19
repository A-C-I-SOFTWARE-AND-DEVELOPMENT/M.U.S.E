import { Box, Text, useStdout } from '@hermes/ink'
import { useEffect, useState } from 'react'
import unicodeSpinners from 'unicode-animations'

import { artWidth, caduceus, CADUCEUS_WIDTH, logo, LOGO_WIDTH } from '../banner.js'
import { flat } from '../lib/text.js'
import type { Theme, ThemeColors } from '../theme.js'
import type { PanelSection, SessionInfo } from '../types.js'

import { readMuseAgentMode } from './appChrome.js'

const LOADER_TICK_MS = 120

// ── Spectral banner shimmer (animation-spec.md, TUI section) ─────────
// Hue-cycle the banner's art rows through the theme's violet→magenta
// accent band on a ~90ms tick, starting on mount and settling back to
// the exact theme palette after ~12s (interval cleared). Re-arms when
// the terminal width or theme changes the banner.

const SHIMMER_TICK_MS = 90
const SHIMMER_SETTLE_MS = 12_000

/** Ping-pong path through the 4-stop ramp: violet → magenta → back. */
const RAMP_PATH = [0, 1, 2, 3, 2, 1] as const

// Tiny HSL helpers, local to this file, so the cycle stays within
// theme-consistent shades (derived from t.color.accent / accentDim)
// instead of hardcoded hex stops that would break the light theme.
function hexToHsl(hex: string): [number, number, number] {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex.trim())

  if (!m) {
    return [275, 0.5, 0.7] // Singularity violet fallback
  }

  const n = parseInt(m[1]!, 16)
  const r = ((n >> 16) & 255) / 255
  const g = ((n >> 8) & 255) / 255
  const b = (n & 255) / 255
  const max = Math.max(r, g, b)
  const min = Math.min(r, g, b)
  const l = (max + min) / 2

  if (max === min) {
    return [275, 0, l] // achromatic: anchor hue in the violet band
  }

  const d = max - min
  const s = l > 0.5 ? d / (2 - max - min) : d / (max + min)
  let h: number

  if (max === r) {
    h = (g - b) / d + (g < b ? 6 : 0)
  } else if (max === g) {
    h = (b - r) / d + 2
  } else {
    h = (r - g) / d + 4
  }

  return [h * 60, s, l]
}

function hslToHex(h: number, s: number, l: number): string {
  const hue = ((h % 360) + 360) % 360
  const c = (1 - Math.abs(2 * l - 1)) * Math.min(1, Math.max(0, s))
  const x = c * (1 - Math.abs(((hue / 60) % 2) - 1))
  const m = l - c / 2
  let r = 0
  let g = 0
  let b = 0

  if (hue < 60) {
    r = c; g = x
  } else if (hue < 120) {
    r = x; g = c
  } else if (hue < 180) {
    g = c; b = x
  } else if (hue < 240) {
    g = x; b = c
  } else if (hue < 300) {
    r = x; b = c
  } else {
    r = c; b = x
  }

  const to = (v: number) => Math.round((v + m) * 255).toString(16).padStart(2, '0')

  return `#${to(r)}${to(g)}${to(b)}`
}

/**
 * 4-stop violet→magenta band anchored on the theme's ONE accent family:
 * accentDim → midpoint → accent → accent hue-rotated ~26° toward magenta
 * (dark: ≈#7E5FA8 → #C187FF → #D8B4FE → #F8B4FE; light theme stays
 * darker/readable because it derives from its own accent stops).
 */
function spectralRamp(c: ThemeColors): string[] {
  const accent = c.accent
  const dim = c.accentDim ?? c.accent
  const [hA, sA, lA] = hexToHsl(accent)
  const [hD, sD, lD] = hexToHsl(dim)
  const mid = hslToHex((hD + hA) / 2, Math.max(sA, sD) + 0.08, Math.min(0.85, (lD + lA) / 2 + 0.08))
  const magenta = hslToHex(hA + 26, sA, lA)

  return [dim, mid, accent, magenta]
}

/**
 * Shimmer frame driver. Returns a frame index ≥ 0 while cycling and -1
 * once settled (final palette frame). Restarts from frame 0 whenever any
 * re-arm input changes (e.g. terminal columns, theme object); the
 * interval is always cleared on settle and on unmount.
 */
export function useSpectralShimmer(...rearm: readonly unknown[]): number {
  const [frame, setFrame] = useState(0)

  useEffect(() => {
    setFrame(0)
    const started = Date.now()
    const id = setInterval(() => {
      if (Date.now() - started >= SHIMMER_SETTLE_MS) {
        clearInterval(id)
        setFrame(-1)
      } else {
        setFrame(n => n + 1)
      }
    }, SHIMMER_TICK_MS)

    return () => clearInterval(id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, rearm)

  return frame
}

/**
 * Apply one shimmer frame to art lines: each colored row steps through
 * the ramp, phase-offset by row index so a wave travels down the art.
 * Uncolored segments (color === '') pass through untouched. frame < 0
 * returns the lines unchanged (settled = exact theme palette).
 */
export function shimmerLines(lines: [string, string][], c: ThemeColors, frame: number): [string, string][] {
  if (frame < 0) {
    return lines
  }

  const ramp = spectralRamp(c)

  return lines.map(([color, text], i) => {
    if (!color) {
      return [color, text]
    }

    return [ramp[RAMP_PATH[(frame + i) % RAMP_PATH.length]!]!, text]
  })
}

function InlineLoader({ label, t }: { label: string; t: Theme }) {
  const [tick, setTick] = useState(0)
  const spinner = unicodeSpinners.braille
  const frame = spinner.frames[tick % spinner.frames.length] ?? '⠋'

  useEffect(() => {
    const id = setInterval(() => setTick(n => n + 1), Math.max(LOADER_TICK_MS, spinner.interval))

    return () => clearInterval(id)
  }, [spinner.interval])

  return (
    <Text color={t.color.muted} wrap="truncate">
      <Text color={t.color.accent}>{frame}</Text> {label}
    </Text>
  )
}

export function ArtLines({ lines }: { lines: [string, string][] }) {
  return (
    <>
      {lines.map(([c, text], i) => (
        <Text color={c} key={i}>
          {text}
        </Text>
      ))}
    </>
  )
}

export function Banner({ t }: { t: Theme }) {
  const cols = useStdout().stdout?.columns ?? 80
  const logoLines = logo(t.color, t.bannerLogo || undefined)
  // Spectral shimmer: hue-cycle the banner art rows through the theme's
  // violet→magenta band (90ms tick), settling to the exact theme palette
  // after ~12s. Re-arms when width or theme changes the banner. Static
  // text (brand fallback, tagline) is never shimmered.
  const frame = useSpectralShimmer(cols, t)
  const lines = shimmerLines(logoLines, t.color, frame)

  return (
    <Box flexDirection="column" marginBottom={1}>
      {cols >= (t.bannerLogo ? artWidth(logoLines) : LOGO_WIDTH) ? (
        <ArtLines lines={lines} />
      ) : (
        <Text bold color={t.color.primary}>
          {t.brand.icon} {t.brand.name}
        </Text>
      )}

      <Text color={t.color.muted}>{t.brand.icon} {t.brand.tagline}</Text>
    </Box>
  )
}

// ── Collapsible helpers ──────────────────────────────────────────────

function CollapseToggle({
  count,
  open,
  suffix,
  t,
  title,
  onToggle
}: {
  count?: number
  open: boolean
  suffix?: string
  t: Theme
  title: string
  onToggle: () => void
}) {
  return (
    <Box onClick={onToggle}>
      <Text color={t.color.accent}>{open ? '▾ ' : '▸ '}</Text>
      <Text bold color={t.color.accent}>
        {title}
      </Text>
      {typeof count === 'number' ? (
        <Text color={t.color.muted}> ({count})</Text>
      ) : null}
      {suffix ? (
        <Text color={t.color.muted}> {suffix}</Text>
      ) : null}
    </Box>
  )
}

// ── SessionPanel ─────────────────────────────────────────────────────

const SKILLS_MAX = 8
const TOOLSETS_MAX = 8

export function SessionPanel({ info, sid, t }: SessionPanelProps) {
  const cols = useStdout().stdout?.columns ?? 100
  const rows = useStdout().stdout?.rows ?? 24
  const heroLines = caduceus(t.color, t.bannerHero || undefined)
  // Spectral shimmer on the hero caduceus, same contract as Banner: the hook
  // is hoisted here (NOT inline in the `{wide && …}` JSX below) because that
  // block is conditionally rendered — an inline hook would break the rules
  // of hooks when `wide` flips. Settles to the exact theme palette ~12s.
  const heroFrame = useSpectralShimmer(cols, t)
  const leftW = Math.min((artWidth(heroLines) || CADUCEUS_WIDTH) + 4, Math.floor(cols * 0.4))
  const wide = cols >= 90 && leftW + 40 < cols
  // The 14-row hero glyph only earns its vertical space on tall terminals;
  // on standard 24-30 row consoles it would push the composer off-screen.
  const showHero = wide && rows >= 40
  const w = Math.max(20, showHero ? cols - leftW - 14 : cols - 12)
  const lineBudget = Math.max(12, w - 2)
  const strip = (s: string) => (s.endsWith('_tools') ? s.slice(0, -6) : s)

  // ── Local collapse state for each section ──
  // All sections default COLLAPSED so the intro panel stays compact enough
  // that the composer is reachable without scrolling on standard consoles.
  const [toolsOpen, setToolsOpen] = useState(false)
  const [skillsOpen, setSkillsOpen] = useState(false)
  const [systemOpen, setSystemOpen] = useState(false)
  const [mcpOpen, setMcpOpen] = useState(false)

  const truncLine = (pfx: string, items: string[]) => {
    let line = ''
    let shown = 0

    for (const item of [...items].sort()) {
      const next = line ? `${line}, ${item}` : item

      if (pfx.length + next.length > lineBudget) {
        return line ? `${line}, …+${items.length - shown}` : `${item}, …`
      }

      line = next
      shown++
    }

    return line
  }

  // ── Collapsible skills section ──
  const skillEntries = Object.entries(info.skills).sort()
  const skillsTotal = flat(info.skills).length
  const skillsCatCount = skillEntries.length

  const skillsBody = () => {
    if (info.lazy && skillEntries.length === 0) {
      return <InlineLoader label="scanning skills" t={t} />
    }

    const shown = skillEntries.slice(0, SKILLS_MAX)
    const overflow = skillEntries.length - SKILLS_MAX

    return (
      <>
        {shown.map(([k, vs]) => (
          <Text key={k} wrap="truncate">
            <Text color={t.color.muted}>{strip(k)}: </Text>
            <Text color={t.color.text}>{truncLine(strip(k) + ': ', vs)}</Text>
          </Text>
        ))}
        {overflow > 0 && (
          <Text color={t.color.muted}>(and {overflow} more categories…)</Text>
        )}
      </>
    )
  }

  // ── Collapsible tools section ──
  const toolEntries = Object.entries(info.tools).sort()
  const toolsTotal = flat(info.tools).length

  const toolsBody = () => {
    const shown = toolEntries.slice(0, TOOLSETS_MAX)
    const overflow = toolEntries.length - TOOLSETS_MAX

    return (
      <>
        {shown.map(([k, vs]) => (
          <Text key={k} wrap="truncate">
            <Text color={t.color.muted}>{strip(k)}: </Text>
            <Text color={t.color.text}>{truncLine(strip(k) + ': ', vs)}</Text>
          </Text>
        ))}
        {overflow > 0 && (
          <Text color={t.color.muted}>(and {overflow} more toolsets…)</Text>
        )}
      </>
    )
  }

  // ── Collapsible MCP section ──
  const mcpBody = () => (
    <>
      {(info.mcp_servers ?? []).map(s => (
        <Text key={s.name} wrap="truncate">
          <Text color={t.color.muted}>{`  ${s.name} `}</Text>
          <Text color={t.color.muted}>{`[${s.transport}]`}</Text>
          <Text color={t.color.muted}>: </Text>
          {s.connected ? (
            <Text color={t.color.text}>
              {s.tools} tool{s.tools === 1 ? '' : 's'}
            </Text>
          ) : (
            <Text color={t.color.error}>failed</Text>
          )}
        </Text>
      ))}
    </>
  )

  // ── System prompt body ──
  const sysPromptLen = (info.system_prompt ?? '').length

  // Defensive capability read for the banner's MOA/◈Fusion availability
  // segments — supplied later by the integrator's globalThis.__museAgentMode.
  const caps = readMuseAgentMode()

  const systemBody = () => {
    if (sysPromptLen === 0) {
      return <Text color={t.color.muted}>No system prompt loaded.</Text>
    }

    return (
      <Text color={t.color.muted}>
        {info.system_prompt}
      </Text>
    )
  }

  return (
    <Box borderColor={t.color.border} borderStyle="round" marginBottom={1} paddingX={2} paddingY={0}>
      {showHero && (
        <Box flexDirection="column" marginRight={2} width={leftW}>
          <ArtLines lines={shimmerLines(heroLines, t.color, heroFrame)} />
          <Text />

          {sid && (
            <Text>
              <Text color={t.color.sessionLabel}>Session: </Text>
              <Text color={t.color.sessionBorder}>{sid}</Text>
            </Text>
          )}
        </Box>
      )}

      <Box flexDirection="column" width={w}>
        {/* Singularity banner line (design.md 1.1):
            name v{version} · model · cwd · N skills · MOA ✓ · ◈Fusion ✓
            MOA/Fusion segments render only when the defensive agent-mode
            getter reports capability flags (see appChrome.tsx). */}
        <Box justifyContent="center" marginBottom={1}>
          <Text wrap="truncate-end">
            <Text bold color={t.color.primary}>
              {t.brand.name}
              {info.version ? ` v${info.version}` : ''}
            </Text>
            {info.release_date ? <Text color={t.color.muted}> ({info.release_date})</Text> : null}
            <Text color={t.color.faint ?? t.color.border}> · </Text>
            <Text color={t.color.accent}>{info.model.split('/').pop()}</Text>
            <Text color={t.color.faint ?? t.color.border}> · </Text>
            <Text color={t.color.muted}>{info.cwd || process.cwd()}</Text>
            <Text color={t.color.faint ?? t.color.border}> · </Text>
            <Text color={t.color.text}>{skillsTotal} skills</Text>
            {typeof caps.moaAvailable === 'boolean' ? (
              <>
                <Text color={t.color.faint ?? t.color.border}> · </Text>
                <Text color={caps.moaAvailable ? t.color.ok : t.color.muted}>
                  MOA {caps.moaAvailable ? '✓' : '✖'}
                </Text>
              </>
            ) : null}
            {typeof caps.fusionAvailable === 'boolean' ? (
              <>
                <Text color={t.color.faint ?? t.color.border}> · </Text>
                <Text color={caps.fusionAvailable ? t.color.ok : t.color.muted}>
                  ◈Fusion {caps.fusionAvailable ? '✓' : '✖'}
                </Text>
              </>
            ) : null}
          </Text>
        </Box>

        {/* ── Tools (collapsed by default) ── */}
        <Box flexDirection="column" marginTop={1}>
          <CollapseToggle
            onToggle={() => setToolsOpen(v => !v)}
            open={toolsOpen}
            t={t}
            title="Available Tools"
          />
          {toolsOpen && toolsBody()}
        </Box>

        {/* ── Skills (collapsed by default) ── */}
        <Box flexDirection="column" marginTop={1}>
          <CollapseToggle
            count={skillsTotal}
            onToggle={() => setSkillsOpen(v => !v)}
            open={skillsOpen}
            suffix={skillsCatCount > 0 ? `in ${skillsCatCount} categor${skillsCatCount === 1 ? 'y' : 'ies'}` : undefined}
            t={t}
            title="Available Skills"
          />
          {skillsOpen && skillsBody()}
        </Box>

        {/* ── System Prompt (collapsed by default) ── */}
        {sysPromptLen > 0 && (
          <Box flexDirection="column" marginTop={1}>
            <CollapseToggle
              onToggle={() => setSystemOpen(v => !v)}
              open={systemOpen}
              suffix={`— ${sysPromptLen.toLocaleString()} chars`}
              t={t}
              title="System Prompt"
            />
            {systemOpen && systemBody()}
          </Box>
        )}

        {/* ── MCP Servers (collapsed by default) ── */}
        {info.mcp_servers && info.mcp_servers.length > 0 && (
          <Box flexDirection="column" marginTop={1}>
            <CollapseToggle
              count={info.mcp_servers.length}
              onToggle={() => setMcpOpen(v => !v)}
              open={mcpOpen}
              suffix="connected"
              t={t}
              title="MCP Servers"
            />
            {mcpOpen && mcpBody()}
          </Box>
        )}

        <Text />

        <Text color={t.color.text}>
          {toolsTotal} tools{' · '}
          {skillsTotal} skills
          {info.mcp_servers?.length ? ` · ${info.mcp_servers.length} MCP` : ''}
          {' · '}
          <Text color={t.color.muted}>/help for commands</Text>
        </Text>

        {typeof info.update_behind === 'number' && info.update_behind > 0 && (
          <Text bold color={t.color.warn}>
            ! {info.update_behind} {info.update_behind === 1 ? 'commit' : 'commits'} behind
            <Text bold={false} color={t.color.warn} dimColor>
              {' '}
              - run{' '}
            </Text>
            <Text bold color={t.color.warn}>
              {info.update_command || 'hermes update'}
            </Text>
            <Text bold={false} color={t.color.warn} dimColor>
              {' '}
              to update
            </Text>
          </Text>
        )}
      </Box>
    </Box>
  )
}

export function Panel({ sections, t, title }: PanelProps) {
  return (
    <Box borderColor={t.color.border} borderStyle="round" flexDirection="column" paddingX={2} paddingY={1}>
      <Box justifyContent="center" marginBottom={1}>
        <Text bold color={t.color.primary}>
          {title}
        </Text>
      </Box>

      {sections.map((sec, si) => (
        <Box flexDirection="column" key={si} marginTop={si > 0 ? 1 : 0}>
          {sec.title && (
            <Text bold color={t.color.accent}>
              {sec.title}
            </Text>
          )}

          {sec.rows?.map(([k, v], ri) => (
            <Text key={ri} wrap="truncate">
              <Text color={t.color.muted}>{k.padEnd(20)}</Text>
              <Text color={t.color.text}>{v}</Text>
            </Text>
          ))}

          {sec.items?.map((item, ii) => (
            <Text color={t.color.text} key={ii} wrap="truncate">
              {item}
            </Text>
          ))}

          {sec.text && <Text color={t.color.muted}>{sec.text}</Text>}
        </Box>
      ))}
    </Box>
  )
}

interface PanelProps {
  sections: PanelSection[]
  t: Theme
  title: string
}

interface SessionPanelProps {
  info: SessionInfo
  sid?: string | null
  t: Theme
}
