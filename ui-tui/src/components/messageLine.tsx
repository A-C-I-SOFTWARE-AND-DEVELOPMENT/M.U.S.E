import { Ansi, Box, NoSelect, Text } from '@hermes/ink'
import { memo, useEffect, useState, type ReactNode } from 'react'

import { LONG_MSG } from '../config/limits.js'
import { sectionMode } from '../domain/details.js'
import { userDisplay } from '../domain/messages.js'
import { ROLE } from '../domain/roles.js'
import { transcriptBodyWidth, transcriptGutterWidth } from '../lib/inputMetrics.js'
import {
  boundedLiveRenderText,
  compactPreview,
  formatToolCall,
  hasAnsi,
  isPasteBackedText,
  parseToolTrailResultLine,
  sanitizeAnsiForRender,
  splitToolDuration,
  stripAnsi,
  toolTrailLabel
} from '../lib/text.js'
import type { Theme } from '../theme.js'
import type { ActiveTool, DetailsMode, Msg, SectionVisibility } from '../types.js'

import { Md } from './markdown.js'
import { StreamingMd } from './streamingMarkdown.js'
import { Spinner, ToolTrail } from './thinking.js'
import { TodoPanel } from './todoPanel.js'

// Collapse threshold for long system messages (system prompt etc.)
const SYSTEM_COLLAPSE_CHARS = 400

// Genre grammar (design.md Part 0): tool = `⏺`, tool-result = `⎿`, agents = `⚙`.
const TOOL_GLYPH = '⏺'
const RESULT_GLYPH = '⎿'
const AGENT_GLYPH = '⚙'

const fmtElapsed = (ms: number) => {
  const sec = Math.max(0, ms) / 1000

  return sec < 10 ? `${sec.toFixed(1)}s` : `${Math.round(sec)}s`
}

// Inline diff-stat coloring (design.md §1.3D): `+N` → ok, `−M` → err.
// Accepts the contract's U+2212 minus; an ASCII `-M` only counts when the
// same string already carries a `+N` stat so negative numbers in prose
// previews ("offset -5") don't light up as deletions.
const statChunks = (text: string, t: Theme): ReactNode[] => {
  const re = /\+\d+/.test(text) ? /(\+\d+|−\d+|-\d+)/g : /(\+\d+|−\d+)/g
  const parts = text.split(re)

  return parts.map((part, i) =>
    /^\+\d+$/.test(part) ? (
      <Text color={t.color.ok} key={i}>
        {part}
      </Text>
    ) : /^[−-]\d+$/.test(part) ? (
      <Text color={t.color.error} key={i}>
        {part}
      </Text>
    ) : (
      part
    )
  )
}

const isDelegateLabel = (label: string) => label.startsWith('Delegate')

// ── Collapsed tool shelf (design.md §1.3D) ───────────────────────────
// One-line `⏺ Name(key-arg)` rows in fgDim with the collapsed result
// `⎿ summary` in fgFaint beneath.  Rendered only when the `tools`
// section resolves to `collapsed`; `expanded` keeps the verbose
// ToolTrail tree and `hidden` renders nothing (both handled by callers).
// Delegation rows swap the tool glyph for `⚙`: accent while active,
// fgDim when done, err when failed.

function CollapsedToolShelf({ t, tools = [], trail = [] }: { t: Theme; tools?: ActiveTool[]; trail?: string[] }) {
  const faint = t.color.faint ?? t.color.muted
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    if (!tools.length) {
      return
    }

    const id = setInterval(() => setNow(Date.now()), 500)

    return () => clearInterval(id)
  }, [tools.length])

  const rows: ReactNode[] = []

  for (const [i, line] of trail.entries()) {
    const parsed = parseToolTrailResultLine(line)

    if (parsed) {
      const failed = parsed.mark === '✗'
      const delegate = isDelegateLabel(parsed.call)
      const { duration, label } = splitToolDuration(parsed.call)
      const callColor = failed ? t.color.error : t.color.muted

      rows.push(
        <Box flexDirection="column" key={`ct-${i}`}>
          <Text wrap="truncate-end">
            <Text color={failed ? t.color.error : delegate ? t.color.muted : t.color.muted}>
              {delegate ? AGENT_GLYPH : TOOL_GLYPH}{' '}
            </Text>
            <Text color={callColor}>{label}</Text>
            {duration ? (
              <Text color={faint} dim>
                {duration}
              </Text>
            ) : null}
          </Text>
          {parsed.detail ? (
            <Text color={failed ? t.color.error : faint} dim={!failed} wrap="truncate-end">
              {'  '}
              {RESULT_GLYPH} {statChunks(parsed.detail, t)}
            </Text>
          ) : null}
        </Box>
      )

      continue
    }

    if (line.startsWith('drafting ')) {
      const label = toolTrailLabel(line.slice(9).replace(/…$/, '').trim())

      rows.push(
        <Box flexDirection="column" key={`ct-${i}`}>
          <Text color={t.color.muted} wrap="truncate-end">
            {TOOL_GLYPH} {label}
          </Text>
          <Text color={faint} dim wrap="truncate-end">
            {'  '}
            {RESULT_GLYPH} drafting...
          </Text>
        </Box>
      )

      continue
    }

    if (line === 'analyzing tool output…') {
      rows.push(
        <Text color={faint} dim key={`ct-${i}`} wrap="truncate-end">
          {rows.length ? (
            <>
              <Spinner color={t.color.accent} variant="think" /> {line}
            </>
          ) : (
            line
          )}
        </Text>
      )

      continue
    }

    rows.push(
      <Text color={faint} dim key={`ct-${i}`} wrap="truncate-end">
        {line}
      </Text>
    )
  }

  for (const tool of tools) {
    const label = formatToolCall(tool.name, tool.context || '')
    const delegate = isDelegateLabel(toolTrailLabel(tool.name))

    rows.push(
      <Text key={tool.id} wrap="truncate-end">
        <Spinner color={t.color.accent} variant="tool" />
        <Text color={delegate ? t.color.accent : t.color.muted}>
          {' '}
          {delegate ? `${AGENT_GLYPH} ` : ''}
          {label}
        </Text>
        {tool.startedAt ? (
          <Text color={faint} dim>
            {' '}
            ({fmtElapsed(now - tool.startedAt)})
          </Text>
        ) : null}
      </Text>
    )
  }

  return <Box flexDirection="column">{rows}</Box>
}

export const MessageLine = memo(function MessageLine({
  cols,
  compact,
  detailsMode = 'collapsed',
  detailsModeCommandOverride = false,
  isStreaming = false,
  msg,
  sections,
  t,
  tools = []
}: MessageLineProps) {
  // Per-section overrides win over the global mode, so resolve each section
  // we might consume here once and gate visibility on the *content-bearing*
  // sections only — never on the global mode.  A `trail` message feeds Tool
  // calls + Activity; an assistant message with thinking/tools metadata
  // feeds Thinking + Tool calls.  Gating on every section would let
  // `thinking` (expanded by default) keep an empty wrapper alive when only
  // `tools` is hidden — exactly the empty-Box bug Copilot caught.
  const thinkingMode = sectionMode('thinking', detailsMode, sections, detailsModeCommandOverride)
  const toolsMode = sectionMode('tools', detailsMode, sections, detailsModeCommandOverride)
  const activityMode = sectionMode('activity', detailsMode, sections, detailsModeCommandOverride)
  const thinking = msg.thinking?.trim() ?? ''

  // Singularity additive token (design.md Part 0): faint carries
  // separators, hints and collapsed result summaries.
  const faint = t.color.faint ?? t.color.muted

  // Collapse toggle for long system messages
  const systemIsLong = msg.role === 'system' && msg.text.length > SYSTEM_COLLAPSE_CHARS
  const [systemOpen, setSystemOpen] = useState(false)

  if (msg.kind === 'trail' && msg.todos?.length) {
    return (
      <TodoPanel
        defaultCollapsed={msg.todoCollapsedByDefault}
        incomplete={msg.todoIncomplete}
        t={t}
        todos={msg.todos}
      />
    )
  }

  if (msg.kind === 'trail' && (msg.tools?.length || tools.length || thinking)) {
    if (thinkingMode === 'hidden' && toolsMode === 'hidden' && activityMode === 'hidden') {
      return null
    }

    // Collapsed tools render as genre one-liners here; expanded tools and
    // all thinking stay on the verbose ToolTrail tree.
    const genreShelf = toolsMode === 'collapsed' && Boolean(msg.tools?.length || tools.length)

    return (
      <Box flexDirection="column">
        <ToolTrail
          commandOverride={detailsModeCommandOverride}
          detailsMode={detailsMode}
          reasoning={thinking}
          reasoningTokens={msg.thinkingTokens}
          sections={sections}
          t={t}
          tools={toolsMode === 'collapsed' ? [] : tools}
          toolTokens={msg.toolTokens}
          trail={toolsMode === 'collapsed' ? [] : (msg.tools ?? [])}
        />
        {genreShelf ? <CollapsedToolShelf t={t} tools={tools} trail={msg.tools ?? []} /> : null}
      </Box>
    )
  }

  if (msg.role === 'tool') {
    // Tool-result row: details_mode gates the whole row; collapsed renders
    // the genre `⎿ summary` line (borderless — the one-border budget
    // reserves borders for the composer and modal overlays); expanded keeps
    // the legacy verbose bordered box.
    if (toolsMode === 'hidden') {
      return null
    }

    const maxChars = Math.max(24, cols - 14)
    const stripped = hasAnsi(msg.text) ? stripAnsi(msg.text) : msg.text
    const safeAnsi = hasAnsi(msg.text) ? sanitizeAnsiForRender(msg.text) : msg.text
    const preview = compactPreview(stripped, maxChars) || '(empty tool result)'

    if (toolsMode === 'collapsed') {
      return (
        <Box marginLeft={3}>
          <Text color={faint} dim wrap="truncate-end">
            {RESULT_GLYPH} {statChunks(preview, t)}
          </Text>
        </Box>
      )
    }

    return (
      <Box alignSelf="flex-start" borderColor={t.color.muted} borderStyle="round" marginLeft={3} paddingX={1}>
        {hasAnsi(msg.text) ? (
          <Text wrap="truncate-end">
            <Ansi>{safeAnsi}</Ansi>
          </Text>
        ) : (
          <Text color={t.color.muted} wrap="truncate-end">
            {preview}
          </Text>
        )}
      </Box>
    )
  }

  const { body, glyph, prefix } = ROLE[msg.role](t)
  const gutterWidth = transcriptGutterWidth(msg.role, t.brand.prompt)

  // Genre glyph pass (design.md Part 0 / §1.3D):
  //   user      — `❯` (brand prompt) bold accent, body text in fg
  //   assistant — `●` accent, body stays borderless markdown
  //   system    — `·` faint
  const glyphChar = msg.role === 'assistant' ? '●' : glyph
  const glyphColor =
    msg.role === 'user' || msg.role === 'assistant' ? t.color.accent : msg.role === 'system' ? faint : prefix
  const bodyColor = msg.role === 'user' ? t.color.text : body

  const showDetails =
    (toolsMode !== 'hidden' && Boolean(msg.tools?.length)) || (thinkingMode !== 'hidden' && Boolean(thinking))

  const content = (() => {
    if (msg.kind === 'slash') {
      return <Text color={t.color.muted}>{msg.text}</Text>
    }

    // ── Collapsible long system message (system prompt, AGENTS.md, etc.) ──
    // MUST come before the hasAnsi check — system messages from the backend
    // contain Rich markup escape codes that would otherwise hit <Ansi> full render.
    if (systemIsLong) {
      const firstLine = (msg.text.split('\n')[0] ?? '').trim().slice(0, 120) || '(system message)'

      return (
        <Box flexDirection="column">
          <Box onClick={() => setSystemOpen(v => !v)}>
            <Text color={t.color.accent}>{systemOpen ? '▾ ' : '▸ '}</Text>
            <Text color={t.color.muted}>{firstLine}</Text>
            <Text color={faint} dim>
              {' — '}
              {msg.text.length.toLocaleString()} chars
            </Text>
          </Box>
          {systemOpen && <Ansi>{sanitizeAnsiForRender(msg.text)}</Ansi>}
        </Box>
      )
    }

    if (msg.role !== 'user' && hasAnsi(msg.text)) {
      return <Ansi>{sanitizeAnsiForRender(msg.text)}</Ansi>
    }

    if (msg.role === 'assistant') {
      const bodyWidth = transcriptBodyWidth(cols, msg.role, t.brand.prompt)

      return isStreaming ? (
        // Incremental markdown: split at the last stable block boundary so
        // only the in-flight tail re-tokenizes per delta.  See
        // streamingMarkdown.tsx for the cost model.
        <StreamingMd cols={bodyWidth} compact={compact} t={t} text={boundedLiveRenderText(msg.text)} />
      ) : (
        <Md cols={bodyWidth} compact={compact} t={t} text={msg.text} />
      )
    }

    if (msg.role === 'user' && msg.text.length > LONG_MSG && isPasteBackedText(msg.text)) {
      const [head, ...rest] = userDisplay(msg.text).split('[long message]')

      return (
        <Text color={bodyColor}>
          {head}
          <Text color={faint} dim>
            [long message]
          </Text>
          {rest.join('')}
        </Text>
      )
    }

    return <Text {...(bodyColor ? { color: bodyColor } : {})}>{msg.text}</Text>
  })()

  // Diff segments (emitted by pushInlineDiffSegment between narration
  // segments) need a blank line on both sides so the patch doesn't butt up
  // against the prose around it.
  const isDiffSegment = msg.kind === 'diff'

  // Collapsed tool shelves replace the verbose ToolCall tree for this row;
  // thinking and expanded tools continue through ToolTrail.
  const genreShelf = toolsMode === 'collapsed' && Boolean(msg.tools?.length)

  return (
    <Box
      flexDirection="column"
      marginBottom={msg.role === 'user' || isDiffSegment ? 1 : 0}
      marginTop={msg.role === 'user' || msg.kind === 'slash' || isDiffSegment ? 1 : 0}
    >
      {showDetails && (
        <Box flexDirection="column" marginBottom={1}>
          <ToolTrail
            commandOverride={detailsModeCommandOverride}
            detailsMode={detailsMode}
            reasoning={thinking}
            reasoningTokens={msg.thinkingTokens}
            sections={sections}
            t={t}
            toolTokens={msg.toolTokens}
            trail={toolsMode === 'collapsed' ? [] : msg.tools}
          />
          {genreShelf ? <CollapsedToolShelf t={t} trail={msg.tools ?? []} /> : null}
        </Box>
      )}

      <Box>
        <NoSelect flexShrink={0} fromLeftEdge width={gutterWidth}>
          <Text bold={msg.role === 'user'} color={glyphColor}>
            {glyphChar}{' '}
          </Text>
        </NoSelect>

        <Box width={transcriptBodyWidth(cols, msg.role, t.brand.prompt)}>{content}</Box>
      </Box>
    </Box>
  )
})

interface MessageLineProps {
  cols: number
  compact?: boolean
  detailsMode?: DetailsMode
  detailsModeCommandOverride?: boolean
  isStreaming?: boolean
  msg: Msg
  sections?: SectionVisibility
  t: Theme
  tools?: ActiveTool[]
}
