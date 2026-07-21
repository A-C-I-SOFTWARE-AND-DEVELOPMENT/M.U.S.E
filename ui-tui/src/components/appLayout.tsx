import { AlternateScreen, Box, NoSelect, ScrollBox, Text } from '@hermes/ink'
import { useStore } from '@nanostores/react'
import { Fragment, memo, useMemo, useRef } from 'react'

import { useGateway } from '../app/gatewayContext.js'
import type { AppLayoutProps } from '../app/interfaces.js'
import { $isBlocked, $overlayState, patchOverlayState } from '../app/overlayStore.js'
// Side-effect import: installs globalThis.__museAgentMode at boot and lets
// the composer re-render on Tab agent-mode cycles (design.md rule 8).
import { $agentMode } from '../app/agentModeStore.js'
import { $uiState } from '../app/uiStore.js'
import { INLINE_MODE, SHOW_FPS } from '../config/env.js'
import { PLACEHOLDER } from '../content/placeholders.js'
import {
  COMPOSER_PROMPT_GAP_WIDTH,
  composerPromptWidth,
  inputVisualHeight,
  stableComposerColumns
} from '../lib/inputMetrics.js'
import { PerfPane } from '../lib/perfPane.js'
import { composerPromptText } from '../lib/prompt.js'

import { AgentsOverlay } from './agentsOverlay.js'
import { GoodVibesHeart, StatusRule, StickyPromptTracker, TranscriptScrollbar } from './appChrome.js'
import { FloatingOverlays, PromptZone } from './appOverlays.js'
import { Banner, Panel, SessionPanel } from './branding.js'
import { FpsOverlay } from './fpsOverlay.js'
import { FusionOverlay } from './fusionOverlay.js'
import { HelpHint } from './helpHint.js'
import { MessageLine } from './messageLine.js'
import { composerBorderColor, composerGlyph } from './prompts.js'
import { QueuedMessages } from './queuedMessages.js'
import { LiveTodoPanel, StreamingAssistant } from './streamingAssistant.js'
import { TextInput, type TextInputMouseApi } from './textInput.js'

const PromptPrefix = memo(function PromptPrefix({
  bold = false,
  color,
  promptText,
  width
}: {
  bold?: boolean
  color: string
  promptText: string
  width: number
}) {
  const glyphWidth = Math.max(1, width - COMPOSER_PROMPT_GAP_WIDTH)

  return (
    <Box width={width}>
      <Box width={glyphWidth}>
        <Text bold={bold} color={color}>
          {promptText}
        </Text>
      </Box>
      <Box width={COMPOSER_PROMPT_GAP_WIDTH} />
    </Box>
  )
})

const TranscriptPane = memo(function TranscriptPane({
  actions,
  composer,
  progress,
  transcript
}: Pick<AppLayoutProps, 'actions' | 'composer' | 'progress' | 'transcript'>) {
  const ui = useStore($uiState)

  // LiveTodoPanel rides as a child of the latest user-message row so it
  // visually belongs to the prompt and follows it during scroll. -1 when
  // empty → row.index === -1 is always false → no render.
  const lastUserIdx = useMemo(() => {
    const items = transcript.historyItems

    for (let i = items.length - 1; i >= 0; i--) {
      if (items[i].role === 'user') {
        return i
      }
    }

    return -1
  }, [transcript.historyItems])

  // Index of the first user-role message; every later user message gets a
  // small dash above it so multi-turn transcripts visually segment by
  // turn. -1 when no user message has been sent yet → no separator ever
  // renders.
  const firstUserIdx = useMemo(
    () => transcript.historyItems.findIndex(m => m.role === 'user'),
    [transcript.historyItems]
  )

  return (
    <>
      <ScrollBox
        flexDirection="column"
        flexGrow={1}
        flexShrink={1}
        onClick={(e: { cellIsBlank?: boolean }) => {
          if (e.cellIsBlank) {
            actions.clearSelection()
          }
        }}
        ref={transcript.scrollRef}
        stickyScroll
      >
        <Box flexDirection="column" paddingX={1}>
          {transcript.virtualHistory.topSpacer > 0 ? <Box height={transcript.virtualHistory.topSpacer} /> : null}

          {transcript.virtualRows.slice(transcript.virtualHistory.start, transcript.virtualHistory.end).map(row => (
            <Box flexDirection="column" key={row.key} ref={transcript.virtualHistory.measureRef(row.key)}>
              {row.msg.role === 'user' && firstUserIdx >= 0 && row.index > firstUserIdx && (
                <Box marginTop={1}>
                  <Text color={ui.theme.color.border}>───</Text>
                </Box>
              )}

              {row.msg.kind === 'intro' ? (
                <Box flexDirection="column" paddingTop={1}>
                  <Banner t={ui.theme} />

                  {row.msg.info && <SessionPanel info={row.msg.info} sid={ui.sid} t={ui.theme} />}
                </Box>
              ) : row.msg.kind === 'panel' && row.msg.panelData ? (
                <Panel sections={row.msg.panelData.sections} t={ui.theme} title={row.msg.panelData.title} />
              ) : (
                <MessageLine
                  cols={composer.cols}
                  compact={ui.compact}
                  detailsMode={ui.detailsMode}
                  detailsModeCommandOverride={ui.detailsModeCommandOverride}
                  msg={row.msg}
                  sections={ui.sections}
                  t={ui.theme}
                />
              )}

              {row.index === lastUserIdx && <LiveTodoPanel />}
            </Box>
          ))}

          {transcript.virtualHistory.bottomSpacer > 0 ? <Box height={transcript.virtualHistory.bottomSpacer} /> : null}

          <StreamingAssistant
            cols={composer.cols}
            compact={ui.compact}
            detailsMode={ui.detailsMode}
            detailsModeCommandOverride={ui.detailsModeCommandOverride}
            progress={progress}
            sections={ui.sections}
          />
        </Box>
      </ScrollBox>

      <NoSelect flexShrink={0} marginLeft={1}>
        <TranscriptScrollbar scrollRef={transcript.scrollRef} t={ui.theme} />
      </NoSelect>

      <StickyPromptTracker
        messages={transcript.historyItems}
        offsets={transcript.virtualHistory.offsets}
        onChange={actions.setStickyPrompt}
        scrollRef={transcript.scrollRef}
      />
    </>
  )
})

const ComposerPane = memo(function ComposerPane({
  actions,
  composer,
  status
}: Pick<AppLayoutProps, 'actions' | 'composer' | 'status'>) {
  const ui = useStore($uiState)
  const isBlocked = useStore($isBlocked)
  const overlay = useStore($overlayState)
  // Subscription only: the composer border/glyph helpers read the mode via
  // globalThis.__museAgentMode; subscribing re-renders on Tab mode cycles.
  useStore($agentMode)
  const sh = (composer.inputBuf[0] ?? composer.input).startsWith('!')
  // composerGlyph layers the mode glyphs ($/◈/M) over the profile-aware base
  // prompt text (design.md 1.2).
  const promptText = composerGlyph(composerPromptText(ui.theme.brand.prompt, ui.info?.profile_name, false), sh)
  const promptWidth = composerPromptWidth(promptText)
  const promptBlank = ' '.repeat(promptWidth)
  // The rounded border consumes 2 columns; reserve them so the input keeps
  // its physical wrap width inside the bordered composer.
  const inputColumns = stableComposerColumns(composer.cols - 2, promptWidth)
  const inputHeight = inputVisualHeight(composer.input, inputColumns)
  const inputMouseRef = useRef<null | TextInputMouseApi>(null)

  const captureInputDrag = (e: GutterMouseEvent) => {
    if (e.button !== 0) {
      return
    }

    e.stopImmediatePropagation?.()
    inputMouseRef.current?.startAtBeginning()
  }

  // Drag origin matches the input box's top-left, so localRow / localCol
  // map directly into TextInput coords (after backing out the prompt cell).
  const dragFromPromptRow = (e: GutterMouseEvent) => {
    if (e.button !== 0) {
      return
    }

    e.stopImmediatePropagation?.()
    inputMouseRef.current?.dragAt(e.localRow ?? 0, (e.localCol ?? 0) - promptWidth)
  }

  // Spacer rows live on a different vertical origin; only the column is
  // parent-aligned with the input. Force row=0 so vertical drags can't
  // jump the cursor to the wrong wrapped line.
  const dragFromSpacer = (e: GutterMouseEvent) => {
    if (e.button !== 0) {
      return
    }

    e.stopImmediatePropagation?.()
    inputMouseRef.current?.dragAt(0, (e.localCol ?? 0) - promptWidth)
  }

  const endInputDrag = () => inputMouseRef.current?.end()

  return (
    <NoSelect
      flexDirection="column"
      flexShrink={0}
      fromLeftEdge
      onClick={(e: { cellIsBlank?: boolean }) => {
        if (e.cellIsBlank) {
          actions.clearSelection()
        }
      }}
      paddingX={1}
    >
      <QueuedMessages
        cols={composer.cols}
        queued={composer.queuedDisplay}
        queueEditIdx={composer.queueEditIdx}
        t={ui.theme}
      />

      {ui.bgTasks.size > 0 && (
        <Text color={ui.theme.color.muted}>
          {ui.bgTasks.size} background {ui.bgTasks.size === 1 ? 'task' : 'tasks'} running
        </Text>
      )}

      {status.showStickyPrompt ? (
        <Text color={ui.theme.color.muted} wrap="truncate-end">
          <Text color={ui.theme.color.label}>↳ </Text>

          {status.stickyPrompt}
        </Text>
      ) : (
        <Box height={1} onMouseDown={captureInputDrag} onMouseDrag={dragFromSpacer} onMouseUp={endInputDrag} />
      )}

      <StatusRulePane at="top" composer={composer} status={status} />

      <Box
        borderColor={composerBorderColor(ui.theme, { approvalPending: Boolean(overlay.approval) })}
        borderStyle="round"
        flexDirection="column"
        marginTop={ui.statusBar === 'top' ? 0 : 1}
        position="relative"
      >
        <FloatingOverlays
          cols={composer.cols}
          compIdx={composer.compIdx}
          completions={composer.completions}
          onModelSelect={actions.onModelSelect}
          onPickerSelect={actions.resumeById}
          onRunSlash={actions.runSlash}
          pagerPageSize={composer.pagerPageSize}
        />

        {composer.input === '?' && !composer.inputBuf.length && <HelpHint t={ui.theme} />}

        {!isBlocked && (
          <>
            {composer.inputBuf.map((line, i) => (
              <Box key={i}>
                <Box width={promptWidth}>
                  {i === 0 ? (
                    <PromptPrefix color={ui.theme.color.muted} promptText={promptText} width={promptWidth} />
                  ) : (
                    <Text color={ui.theme.color.muted}>{promptBlank}</Text>
                  )}
                </Box>

                <Text color={ui.theme.color.text}>{line || ' '}</Text>
              </Box>
            ))}

            <Box
              onMouseDown={captureInputDrag}
              onMouseDrag={dragFromPromptRow}
              onMouseUp={endInputDrag}
              position="relative"
              // Bordered composer: 2 cols for the border on top of the outer
              // paddingX, so the input row fits inside the rounded frame.
              width={Math.max(1, composer.cols - 4)}
            >
              <Box width={promptWidth}>
                {sh ? (
                  <PromptPrefix color={ui.theme.color.shellDollar} promptText={promptText} width={promptWidth} />
                ) : composer.inputBuf.length ? (
                  <Text color={ui.theme.color.prompt}>{promptBlank}</Text>
                ) : (
                  <PromptPrefix bold color={ui.theme.color.prompt} promptText={promptText} width={promptWidth} />
                )}
              </Box>

              <Box flexGrow={0} flexShrink={0} height={inputHeight} width={inputColumns}>
                {/* Reserve the transcript scrollbar gutter too so typing never rewraps when the scrollbar column repaints. */}
                <TextInput
                  columns={inputColumns}
                  mouseApiRef={inputMouseRef}
                  onChange={composer.updateInput}
                  onPaste={composer.handleTextPaste}
                  onSubmit={composer.submit}
                  placeholder={composer.empty ? PLACEHOLDER : ui.busy ? 'Ctrl+C to interrupt…' : ''}
                  value={composer.input}
                  voiceRecordKey={composer.voiceRecordKey}
                />
              </Box>

              <Box position="absolute" right={0}>
                <GoodVibesHeart t={ui.theme} tick={status.goodVibesTick} />
              </Box>
            </Box>
          </>
        )}
      </Box>

      {!composer.empty && !ui.sid && <Text color={ui.theme.color.muted}>✦ {ui.status}</Text>}

      <StatusRulePane at="bottom" composer={composer} status={status} />
    </NoSelect>
  )
})

const AgentsOverlayPane = memo(function AgentsOverlayPane() {
  const { gw } = useGateway()
  const ui = useStore($uiState)
  const overlay = useStore($overlayState)

  return (
    <AgentsOverlay
      gw={gw}
      initialHistoryIndex={overlay.agentsInitialHistoryIndex}
      onClose={() => patchOverlayState({ agents: false, agentsInitialHistoryIndex: 0 })}
      t={ui.theme}
    />
  )
})

// Fullscreen fusion/MOA center (design.md 1.3B) — mirrors AgentsOverlayPane:
// a full-screen swap surface, not a float (fusion.manifest.md §4).
const FusionOverlayPane = memo(function FusionOverlayPane() {
  const { gw } = useGateway()
  const ui = useStore($uiState)

  return <FusionOverlay gw={gw} onClose={() => patchOverlayState({ fusion: false })} t={ui.theme} />
})

const StatusRulePane = memo(function StatusRulePane({
  at,
  composer,
  status
}: Pick<AppLayoutProps, 'composer' | 'status'> & { at: 'bottom' | 'top' }) {
  const ui = useStore($uiState)

  if (ui.statusBar !== at) {
    return null
  }

  return (
    <Box marginTop={at === 'top' ? 1 : 0}>
      <StatusRule
        bgCount={ui.bgTasks.size}
        busy={ui.busy}
        cols={composer.cols}
        cwdLabel={status.cwdLabel}
        gitBranch={status.gitBranch ?? undefined}
        model={ui.info?.model ?? ''}
        modelFast={ui.info?.fast || ui.info?.service_tier === 'priority'}
        modelReasoningEffort={ui.info?.reasoning_effort}
        sessionStartedAt={status.sessionStartedAt}
        showCost={ui.showCost}
        status={ui.status}
        statusColor={status.statusColor}
        t={ui.theme}
        turnStartedAt={status.turnStartedAt}
        usage={ui.usage}
        voiceLabel={status.voiceLabel}
      />
    </Box>
  )
})

export const AppLayout = memo(function AppLayout({
  actions,
  composer,
  mouseTracking,
  progress,
  status,
  transcript
}: AppLayoutProps) {
  const overlay = useStore($overlayState)
  const ui = useStore($uiState)

  // Inline mode skips AlternateScreen so the host terminal's native
  // scrollback captures rows scrolled off the top; composer + progress
  // stay anchored via normal flex-column flow.
  const Shell = INLINE_MODE ? Fragment : AlternateScreen
  const shellProps = INLINE_MODE ? {} : { mouseTracking }

  return (
    <Shell {...shellProps}>
      <Box flexDirection="column" flexGrow={1}>
        <Box flexDirection="row" flexGrow={1}>
          {overlay.fusion ? (
            <PerfPane id="fusion">
              <FusionOverlayPane />
            </PerfPane>
          ) : overlay.agents ? (
            <PerfPane id="agents">
              <AgentsOverlayPane />
            </PerfPane>
          ) : (
            <PerfPane id="transcript">
              <TranscriptPane actions={actions} composer={composer} progress={progress} transcript={transcript} />
            </PerfPane>
          )}
        </Box>

        {!overlay.agents && !overlay.fusion && (
          <>
            <PerfPane id="prompt">
              <PromptZone
                cols={composer.cols}
                onApprovalChoice={actions.answerApproval}
                onClarifyAnswer={actions.answerClarify}
                onSecretSubmit={actions.answerSecret}
                onSudoSubmit={actions.answerSudo}
              />
            </PerfPane>

            <PerfPane id="composer">
              <ComposerPane actions={actions} composer={composer} status={status} />
            </PerfPane>

            {SHOW_FPS && (
              <Box flexShrink={0} justifyContent="flex-end" paddingRight={1}>
                <FpsOverlay t={ui.theme} />
              </Box>
            )}
          </>
        )}
      </Box>
    </Shell>
  )
})

type GutterMouseEvent = {
  button: number
  localCol?: number
  localRow?: number
  stopImmediatePropagation?: () => void
}
