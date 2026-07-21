import type { ThemeColors } from './theme.js'

const RICH_RE = /\[(?:bold\s+)?(?:dim\s+)?(#(?:[0-9a-fA-F]{3,8}))\]([\s\S]*?)(\[\/\])/g

export function parseRichMarkup(markup: string): Line[] {
  const lines: Line[] = []

  for (const raw of markup.split('\n')) {
    const trimmed = raw.trimEnd()

    if (!trimmed) {
      lines.push(['', ' '])

      continue
    }

    const matches = [...trimmed.matchAll(RICH_RE)]

    if (!matches.length) {
      lines.push(['', trimmed])

      continue
    }

    let cursor = 0

    for (const m of matches) {
      const before = trimmed.slice(cursor, m.index)

      if (before) {
        lines.push(['', before])
      }

      lines.push([m[1]!, m[2]!])
      cursor = m.index! + m[0].length
    }

    if (cursor < trimmed.length) {
      lines.push(['', trimmed.slice(cursor)])
    }
  }

  return lines
}

// Fallback art (used only when a theme leaves bannerLogo/bannerHero empty —
// e.g. light mode). The dark default renders the faithful per-character
// markup from theme.ts (MUSE_WORDMARK / MUSE_GLYPH). muse block wordmark:
const LOGO_ART = [
  '███╗   ███╗   ██╗   ██╗   ███████╗   ███████╗',
  '████╗ ████║   ██║   ██║   ██╔════╝   ██╔════╝',
  '██╔████╔██║   ██║   ██║   ███████╗   █████╗',
  '██║╚██╔╝██║   ██║   ██║   ╚════██║   ██╔══╝',
  '██║ ╚═╝ ██║██╗╚██████╔╝██╗███████║██╗███████║██╗',
  '╚═╝     ╚═╝╚═╝ ╚═════╝ ╚═╝╚══════╝╚═╝╚══════╝╚═╝'
]

// The Singularity mark: a white core inside concentric rings — an inner
// ring around the core and a thin outer ring with the signature
// lower-right gap.
const CADUCEUS_ART = [
  '        ╭───────╮',
  '     ╭─╯         ╰─╮',
  '   ╭╯    ╭─────╮    ╰╮',
  '  │    ╭╯       ╰╮    │',
  '  │    │    ◉    │    │',
  '  │    ╰╮       ╭╯    │',
  '   ╰╮    ╰─────╯    ╭╯',
  '     ╰─╮',
  '        ╰───────╯'
]

// All wordmark rows are the white core hero (primary). The glyph's ring rows
// take the accent; the core row (index 4) is the white core (primary).
const LOGO_GRADIENT = [0, 0, 0, 0, 0, 0] as const
const CADUC_GRADIENT = [1, 1, 1, 1, 0, 1, 1, 1, 1] as const

const colorize = (art: string[], gradient: readonly number[], c: ThemeColors): Line[] => {
  const p = [c.primary, c.accent, c.border, c.muted]

  return art.map((text, i) => [p[gradient[i]!] ?? c.muted, text])
}

export const LOGO_WIDTH = Math.max(...LOGO_ART.map(line => line.length))
export const CADUCEUS_WIDTH = Math.max(...CADUCEUS_ART.map(line => line.length))

export const logo = (c: ThemeColors, customLogo?: string): Line[] =>
  customLogo ? parseRichMarkup(customLogo) : colorize(LOGO_ART, LOGO_GRADIENT, c)

export const caduceus = (c: ThemeColors, customHero?: string): Line[] =>
  customHero ? parseRichMarkup(customHero) : colorize(CADUCEUS_ART, CADUC_GRADIENT, c)

export const artWidth = (lines: Line[]) => lines.reduce((m, [, t]) => Math.max(m, t.length), 0)

type Line = [string, string]
