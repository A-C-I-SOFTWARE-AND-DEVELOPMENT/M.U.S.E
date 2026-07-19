import { Box, Text, useInput } from '@hermes/ink'
import { useMemo, useState } from 'react'

import type { Theme } from '../theme.js'

import { windowOffset } from './overlayControls.js'

/**
 * Reusable fuzzy-filter list (design.md Part 0 §10: "Everything fuzzy-filters").
 * Pure subsequence scoring, zero dependencies — shared by the command palette
 * (commandPalette.tsx) and the hub browser (hubOverlay.tsx).
 */
export interface FuzzyItem {
  id: string
  label: string
  hint?: string
  category?: string
  keywords?: string
}

const CONTROL_CHAR = /[\x00-\x1f\x7f]/

const WORD_BOUNDARY = new Set([' ', '/', '-', '_', '.', ':', '(', '[', '<'])

const isBoundary = (target: string, index: number) => {
  if (index === 0) {
    return true
  }

  const prev = target.charAt(index - 1)
  const curr = target.charAt(index)

  if (WORD_BOUNDARY.has(prev)) {
    return true
  }

  // camelCase transition: lower → upper
  return prev >= 'a' && prev <= 'z' && curr >= 'A' && curr <= 'Z'
}

/**
 * Subsequence score: every query char must appear in `target` in order.
 * Returns null on no-match; higher is better. Bonuses for matches at the
 * start of the string, on word/camelCase boundaries, and for consecutive
 * runs; shorter targets win ties.
 */
export const fuzzyScore = (query: string, target: string): null | number => {
  if (!query) {
    return 0
  }

  const q = query.toLowerCase()
  const t = target.toLowerCase()

  let score = 0
  let cursor = 0
  let lastMatch = -2
  let streak = 0

  for (let qi = 0; qi < q.length; qi++) {
    const c = q.charAt(qi)
    let found = -1

    for (let ti = cursor; ti < t.length; ti++) {
      if (t.charAt(ti) === c) {
        found = ti

        break
      }
    }

    if (found === -1) {
      return null
    }

    let bonus = 1

    if (isBoundary(target, found)) {
      bonus += found === 0 ? 8 : 5
    }

    if (found === lastMatch + 1) {
      streak++
      bonus += 6 + streak
    } else {
      streak = 0
    }

    score += bonus
    lastMatch = found
    cursor = found + 1
  }

  // Prefer compact targets when scores are otherwise equal.
  score += Math.max(0, 30 - t.length) * 0.1

  return score
}

// Field weights: label dominates, keywords/category assist.
const scoreItem = (item: FuzzyItem, token: string): null | number => {
  const fields: [string, number][] = [
    [item.label, 1],
    [item.keywords ?? '', 0.6],
    [item.category ?? '', 0.35]
  ]

  let best: null | number = null

  for (const [field, weight] of fields) {
    if (!field) {
      continue
    }

    const raw = fuzzyScore(token, field)

    if (raw !== null && (best === null || raw * weight > best)) {
      best = raw * weight
    }
  }

  return best
}

/**
 * Filter + rank items against a query. Space-separated tokens must each match
 * somewhere (label / keywords / category). Empty query returns source order.
 */
export const filterFuzzyItems = (items: FuzzyItem[], query: string): FuzzyItem[] => {
  const tokens = query.trim().toLowerCase().split(/\s+/).filter(Boolean)

  if (!tokens.length) {
    return items.slice()
  }

  const scored: { item: FuzzyItem; score: number }[] = []

  for (const item of items) {
    let total = 0
    let miss = false

    for (const token of tokens) {
      const s = scoreItem(item, token)

      if (s === null) {
        miss = true

        break
      }

      total += s
    }

    if (!miss) {
      scored.push({ item, score: total })
    }
  }

  // Array.prototype.sort is stable — equal scores keep source order.
  scored.sort((a, b) => b.score - a.score)

  return scored.map(s => s.item)
}

type ListRow =
  | { key: string; kind: 'header'; label: string }
  | { flat: number; item: FuzzyItem; key: string; kind: 'item' }

/**
 * Bucket the (possibly score-reordered) filtered items by category so each
 * category renders under a single group header, in first-appearance order.
 * Items without a category render headerless. Empty query keeps source order.
 */
const buildRows = (filtered: FuzzyItem[]): ListRow[] => {
  const buckets = new Map<string | undefined, { flat: number; item: FuzzyItem }[]>()
  const order: (string | undefined)[] = []

  filtered.forEach((item, flat) => {
    const cat = item.category

    if (!buckets.has(cat)) {
      buckets.set(cat, [])
      order.push(cat)
    }

    buckets.get(cat)!.push({ flat, item })
  })

  const anyCategory = order.some(c => c !== undefined)
  const rows: ListRow[] = []

  for (const cat of order) {
    if (anyCategory && cat) {
      rows.push({ key: `h:${cat}`, kind: 'header', label: cat })
    }

    for (const { flat, item } of buckets.get(cat)!) {
      rows.push({ flat, item, key: `${flat}:${item.id}`, kind: 'item' })
    }
  }

  return rows
}

export function FuzzyList({
  footer,
  items,
  maxRows = 10,
  onClose,
  onPick,
  placeholder = 'type to filter…',
  t
}: FuzzyListProps) {
  const [query, setQuery] = useState('')
  const [sel, setSel] = useState(0)

  const faint = t.color.faint ?? t.color.muted
  const filtered = useMemo(() => filterFuzzyItems(items, query), [items, query])
  const clampedSel = filtered.length ? Math.min(sel, filtered.length - 1) : 0

  const updateQuery = (next: string | ((q: string) => string)) => {
    setSel(0)
    setQuery(next)
  }

  useInput((ch, key) => {
    // Esc is sacred (design.md Part 0 §7): closes the topmost overlay.
    if (key.escape) {
      return onClose()
    }

    if (key.return) {
      const item = filtered[clampedSel]

      if (item) {
        onPick(item)
      }

      return
    }

    // fzf-style Ctrl+P/Ctrl+N as aliases for ↑/↓. While this list is open the
    // composer is unmounted ($isBlocked), so these never reach the global map.
    if (key.upArrow || (key.ctrl && ch === 'p')) {
      return setSel(s => Math.max(0, s - 1))
    }

    if (key.downArrow || (key.ctrl && ch === 'n')) {
      return setSel(s => Math.min(filtered.length - 1, s + 1))
    }

    if (key.pageUp) {
      return setSel(s => Math.max(0, s - maxRows))
    }

    if (key.pageDown) {
      return setSel(s => Math.min(filtered.length - 1, s + maxRows))
    }

    if (key.home) {
      return setSel(0)
    }

    if (key.end) {
      return setSel(Math.max(0, filtered.length - 1))
    }

    if (key.backspace || key.delete) {
      return updateQuery(q => Array.from(q).slice(0, -1).join(''))
    }

    // Everything with a modifier or special-key flag is not filter text.
    if (key.ctrl || key.meta || key.super || key.tab || key.fn) {
      return
    }

    if (!ch || CONTROL_CHAR.test(ch)) {
      return
    }

    updateQuery(q => q + ch)
  })

  const rows = useMemo(() => buildRows(filtered), [filtered])
  const selRow = rows.findIndex(r => r.kind === 'item' && r.flat === clampedSel)
  const offset = windowOffset(rows.length, Math.max(0, selRow), maxRows)
  const visible = rows.slice(offset, offset + maxRows)
  const below = rows.length - offset - visible.length

  return (
    <Box flexDirection="column" width="100%">
      <Box marginBottom={1}>
        <Text color={t.color.accent}>{'❯ '}</Text>
        {query ? (
          <Text color={t.color.text}>
            {query}
            <Text color={t.color.accent}>▌</Text>
          </Text>
        ) : (
          <Text color={faint}>
            {placeholder}
            <Text color={t.color.accent}>▌</Text>
          </Text>
        )}
      </Box>

      {offset > 0 && <Text color={faint}>{`  ↑ ${offset} more`}</Text>}

      {visible.map(row => {
        if (row.kind === 'header') {
          return (
            <Text color={faint} key={row.key} wrap="truncate-end">
              {'  '}
              {row.label}
            </Text>
          )
        }

        const selected = row.flat === clampedSel

        return (
          // selectionBg is the Singularity bgMute token (#16161D dark) —
          // design.md Part 0: selected row = bgMute fill + accent ❯ glyph.
          // Mouse: hover moves the cursor to this row (same setSel the ↑/↓
          // keys drive, so keyboard and pointer never diverge); click picks.
          <Box
            backgroundColor={selected ? t.color.selectionBg : undefined}
            key={row.key}
            onClick={() => onPick(row.item)}
            onMouseEnter={() => setSel(row.flat)}
            width="100%"
          >
            <Text wrap="truncate-end">
              <Text color={selected ? t.color.accent : faint}>{selected ? '❯ ' : '  '}</Text>
              <Text color={t.color.text}>{row.item.label}</Text>
              {row.item.hint ? <Text color={faint}>{`  ${row.item.hint}`}</Text> : null}
            </Text>
          </Box>
        )
      })}

      {below > 0 && <Text color={faint}>{`  ↓ ${below} more`}</Text>}

      {!filtered.length && (
        <Text color={faint}>{query ? `no matches for “${query}”` : 'no items'}</Text>
      )}

      {footer && (
        <Box marginTop={1}>
          <Text color={faint} wrap="truncate-end">
            {footer}
          </Text>
        </Box>
      )}
    </Box>
  )
}

interface FuzzyListProps {
  items: FuzzyItem[]
  onPick: (item: FuzzyItem) => void
  onClose: () => void
  footer?: string
  maxRows?: number
  placeholder?: string
  t: Theme
}
