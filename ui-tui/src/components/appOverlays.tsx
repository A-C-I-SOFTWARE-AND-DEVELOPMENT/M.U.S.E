import { Box, stringWidth, Text } from '@hermes/ink'
import { useStore } from '@nanostores/react'
import type { ReactNode } from 'react'

import { useGateway } from '../app/gatewayContext.js'
import type { AppOverlaysProps, OverlayState } from '../app/interfaces.js'
import type { FloatingOverlayId } from '../app/overlayRegistry.js'
import { FLOATING_OVERLAY_IDS } from '../app/overlayRegistry.js'
import { $overlayState, hasFloatingPanel, patchOverlayState } from '../app/overlayStore.js'
import { $uiSessionId, $uiTheme } from '../app/uiStore.js'
import type { Theme } from '../theme.js'

import { ActiveSessionSwitcher } from './activeSessionSwitcher.js'
import { FloatBox } from './appChrome.js'
import { BillingOverlay } from './billingOverlay.js'
import { MaskedPrompt } from './maskedPrompt.js'
import { ModelPicker } from './modelPicker.js'
import { OverlayHint } from './overlayControls.js'
import { listRowStyle } from './overlayPrimitives.js'
import { PetPicker } from './petPicker.js'
import { PluginsHub } from './pluginsHub.js'
import { ApprovalPrompt, ClarifyPrompt, ConfirmPrompt } from './prompts.js'
import { SkillsHub } from './skillsHub.js'
import { SubscriptionOverlay } from './subscriptionOverlay.js'
import { WidgetGrid, type WidgetGridWidget } from './widgetGrid.js'

const COMPLETION_WINDOW = 16

/**
 * A prompt hosted in a single-cell WidgetGrid with the classic 1-cell padding.
 * The inner full-width column restores the horizontal stretch the old plain
 * padded Box gave its child, so rendering is identical; routing through the
 * grid makes the prompt zone a layout-engine surface like the desktop app's
 * pane shell.
 */
function PromptCell({ children, cols, id }: { children: ReactNode; cols: number; id: string }) {
  return (
    <Box flexDirection="column" flexShrink={0}>
      <WidgetGrid
        cols={cols}
        columns={1}
        gap={0}
        paddingX={1}
        paddingY={1}
        rowGap={0}
        widgets={[
          {
            children: (
              <Box flexDirection="column" width="100%">
                {children}
              </Box>
            ),
            id
          }
        ]}
      />
    </Box>
  )
}

export function PromptZone({
  cols,
  onApprovalChoice,
  onClarifyAnswer,
  onClarifyQuestionAnswer,
  onSecretSubmit,
  onSudoSubmit
}: Pick<
  AppOverlaysProps,
  'cols' | 'onApprovalChoice' | 'onClarifyAnswer' | 'onClarifyQuestionAnswer' | 'onSecretSubmit' | 'onSudoSubmit'
>) {
  const overlay = useStore($overlayState)
  const theme = useStore($uiTheme)

  if (overlay.approval) {
    return (
      <PromptCell cols={cols} id="approval">
        <ApprovalPrompt cols={cols} onChoice={onApprovalChoice} req={overlay.approval} t={theme} />
      </PromptCell>
    )
  }

  if (overlay.billing) {
    const current = overlay.billing

    const onPatch = (next: Partial<typeof current>) =>
      patchOverlayState(prev => (prev.billing ? { ...prev, billing: { ...prev.billing, ...next } } : prev))

    const onClose = () => patchOverlayState({ billing: null })

    return (
      <PromptCell cols={cols} id="billing">
        <BillingOverlay onClose={onClose} onPatch={onPatch} overlay={current} t={theme} />
      </PromptCell>
    )
  }

  if (overlay.subscription) {
    const current = overlay.subscription

    const onPatch = (next: Partial<typeof current>) =>
      patchOverlayState(prev =>
        prev.subscription ? { ...prev, subscription: { ...prev.subscription, ...next } } : prev
      )

    const onClose = () => patchOverlayState({ subscription: null })

    return (
      <PromptCell cols={cols} id="subscription">
        <SubscriptionOverlay onClose={onClose} onPatch={onPatch} overlay={current} t={theme} />
      </PromptCell>
    )
  }

  if (overlay.confirm) {
    const req = overlay.confirm

    const onConfirm = () => {
      patchOverlayState({ confirm: null })
      req.onConfirm()
    }

    const onCancel = () => patchOverlayState({ confirm: null })

    return (
      <PromptCell cols={cols} id="confirm">
        <ConfirmPrompt onCancel={onCancel} onConfirm={onConfirm} req={req} t={theme} />
      </PromptCell>
    )
  }

  if (overlay.clarify) {
    return (
      <PromptCell cols={cols} id="clarify">
        <ClarifyPrompt
          cols={cols}
          onAnswer={onClarifyAnswer}
          onCancel={() => onClarifyAnswer('')}
          onQuestionAnswer={onClarifyQuestionAnswer}
          req={overlay.clarify}
          t={theme}
        />
      </PromptCell>
    )
  }

  if (overlay.sudo) {
    return (
      <PromptCell cols={cols} id="sudo">
        <MaskedPrompt cols={cols} icon="🔐" label="sudo password required" onSubmit={onSudoSubmit} t={theme} />
      </PromptCell>
    )
  }

  if (overlay.secret) {
    return (
      <PromptCell cols={cols} id="secret">
        <MaskedPrompt
          cols={cols}
          icon="🔑"
          label={overlay.secret.prompt}
          onSubmit={onSecretSubmit}
          sub={`for ${overlay.secret.envVar}`}
          t={theme}
        />
      </PromptCell>
    )
  }

  return null
}

/** Everything a floating panel's renderer needs; assembled once per render. */
interface FloatingOverlayCtx extends Pick<
  AppOverlaysProps,
  | 'onActiveSessionClose'
  | 'onActiveSessionSelect'
  | 'onModelSelect'
  | 'onNewLiveSession'
  | 'onNewPromptSession'
  | 'onResumeSelect'
  | 'pagerPageSize'
> {
  gw: ReturnType<typeof useGateway>['gw']
  overlay: OverlayState
  sid: ReturnType<(typeof $uiSessionId)['get']>
  t: Theme
}

/**
 * One renderer per `floating: true` entry in OVERLAY_REGISTRY. `Record` over
 * `FloatingOverlayId` is the enforcement: declare a floating overlay in the
 * registry and this table stops typechecking until its panel exists. A
 * renderer may return null when the open value carries no payload to draw.
 */
const FLOATING_OVERLAY_RENDERERS: Record<FloatingOverlayId, (ctx: FloatingOverlayCtx) => null | WidgetGridWidget> = {
  modelPicker: ctx => {
    const initialRefresh = typeof ctx.overlay.modelPicker === 'object' && ctx.overlay.modelPicker.refresh === true

    return {
      id: 'model-picker',
      render: width => (
        <FloatBox color={ctx.t.color.border}>
          <ModelPicker
            gw={ctx.gw}
            initialRefresh={initialRefresh}
            maxWidth={width}
            onCancel={() => patchOverlayState({ modelPicker: false })}
            onSelect={ctx.onModelSelect}
            sessionId={ctx.sid}
            t={ctx.t}
          />
        </FloatBox>
      )
    }
  },

  pager: ctx => {
    const pager = ctx.overlay.pager

    if (!pager) {
      return null
    }

    const pagerPageSize = ctx.pagerPageSize

    return {
      id: 'pager',
      render: () => (
        <FloatBox color={ctx.t.color.border}>
          <Box flexDirection="column" paddingX={1} paddingY={1}>
            {pager.title && (
              <Box justifyContent="center" marginBottom={1}>
                <Text bold color={ctx.t.color.primary}>
                  {pager.title}
                </Text>
              </Box>
            )}

            {pager.lines.slice(pager.offset, pager.offset + pagerPageSize).map((line, i) => (
              <Text key={i}>{line}</Text>
            ))}

            <Box marginTop={1}>
              <OverlayHint t={ctx.t}>
                {pager.offset + pagerPageSize < pager.lines.length
                  ? `↑↓/jk line · Enter/Space/PgDn page · b/PgUp back · g/G top/bottom · Esc/q close (${Math.min(pager.offset + pagerPageSize, pager.lines.length)}/${pager.lines.length})`
                  : `end · ↑↓/jk · b/PgUp back · g top · Esc/q close (${pager.lines.length} lines)`}
              </OverlayHint>
            </Box>
          </Box>
        </FloatBox>
      )
    }
  },

  petPicker: ctx => ({
    id: 'pet-picker',
    render: width => (
      <FloatBox color={ctx.t.color.border}>
        <PetPicker gw={ctx.gw} maxWidth={width} onClose={() => patchOverlayState({ petPicker: false })} t={ctx.t} />
      </FloatBox>
    )
  }),

  pluginsHub: ctx => ({
    id: 'plugins-hub',
    render: width => (
      <FloatBox color={ctx.t.color.border}>
        <PluginsHub gw={ctx.gw} maxWidth={width} onClose={() => patchOverlayState({ pluginsHub: false })} t={ctx.t} />
      </FloatBox>
    )
  }),

  sessions: ctx => ({
    id: 'sessions',
    render: width => (
      <FloatBox color={ctx.t.color.border}>
        <ActiveSessionSwitcher
          currentSessionId={ctx.sid}
          gw={ctx.gw}
          maxWidth={width}
          onCancel={() => patchOverlayState({ sessions: false })}
          onClose={ctx.onActiveSessionClose}
          onNew={ctx.onNewLiveSession}
          onNewPrompt={ctx.onNewPromptSession}
          onResume={ctx.onResumeSelect}
          onSelect={ctx.onActiveSessionSelect}
          t={ctx.t}
        />
      </FloatBox>
    )
  }),

  skillsHub: ctx => ({
    id: 'skills-hub',
    render: width => (
      <FloatBox color={ctx.t.color.border}>
        <SkillsHub gw={ctx.gw} maxWidth={width} onClose={() => patchOverlayState({ skillsHub: false })} t={ctx.t} />
      </FloatBox>
    )
  })
}

export function FloatingOverlays({
  cols,
  compIdx,
  completions,
  onActiveSessionSelect,
  onActiveSessionClose,
  onModelSelect,
  onNewLiveSession,
  onNewPromptSession,
  onResumeSelect,
  pagerPageSize
}: Pick<
  AppOverlaysProps,
  | 'cols'
  | 'compIdx'
  | 'completions'
  | 'onActiveSessionSelect'
  | 'onActiveSessionClose'
  | 'onModelSelect'
  | 'onNewLiveSession'
  | 'onNewPromptSession'
  | 'onResumeSelect'
  | 'pagerPageSize'
>) {
  const { gw } = useGateway()
  const overlay = useStore($overlayState)
  const sid = useStore($uiSessionId)
  const theme = useStore($uiTheme)

  const hasAny = hasFloatingPanel(overlay) || completions.length

  if (!hasAny) {
    return null
  }

  // Fixed viewport centered on compIdx — previously the slice end was
  // compIdx + 8 so the dropdown grew from 8 rows to 16 as the user scrolled
  // down, bouncing the height on every keystroke.
  const viewportSize = Math.min(COMPLETION_WINDOW, completions.length)

  const start = Math.max(0, Math.min(compIdx - Math.floor(COMPLETION_WINDOW / 2), completions.length - viewportSize))

  // Every floating panel is a widget in a single-column grid. Panels keep
  // their intrinsic (content-hugging) widths inside full-width cells today;
  // multi-column tiling on wide terminals is a `columns`/track change here,
  // not a rewrite. `maxWidth` hands each panel its cell budget — with one
  // column it never binds, so rendering is identical to the pre-grid layout.
  const widgets: WidgetGridWidget[] = []

  const ctx: FloatingOverlayCtx = {
    gw,
    onActiveSessionClose,
    onActiveSessionSelect,
    onModelSelect,
    onNewLiveSession,
    onNewPromptSession,
    onResumeSelect,
    overlay,
    pagerPageSize,
    sid,
    t: theme
  }

  // Paint order is FLOATING_OVERLAY_IDS, i.e. registry declaration order.
  // Panels used to be pushed by a chain of hand-written `if (overlay.x)`
  // blocks; the chain WAS the order, so reordering the source silently
  // reordered the screen.
  for (const id of FLOATING_OVERLAY_IDS) {
    if (!overlay[id]) {
      continue
    }

    const widget = FLOATING_OVERLAY_RENDERERS[id](ctx)

    if (widget) {
      widgets.push(widget)
    }
  }

  if (completions.length) {
    widgets.push({
      id: 'completions',
      render: () => (
        <FloatBox color={theme.color.primary}>
          {/* No painted panel fill: FloatBox is `opaque`, so rows sit on the
              terminal's own background — the one color that is always right
              on a canvas we don't own (a full completionBg fill was the lone
              surface painting its own background, which is why it could
              disagree with every other overlay). Only the ACTIVE row carries
              a selection chip, mirroring the session switcher. */}
          <Box flexDirection="column" width={Math.max(28, cols - 6)}>
            {(() => {
              const visible = completions.slice(start, start + viewportSize)
              // Two-column grid: the name track auto-sizes to the widest
              // visible command, so descriptions align — and wrapped
              // description lines stay inside their own column instead of
              // running under the names.
              const nameW = Math.max(...visible.map(item => stringWidth(item.display))) + 2

              return visible.map((item, i) => {
                const active = start + i === compIdx
                const row = listRowStyle(theme, active)

                return (
                  <Box
                    backgroundColor={row.backgroundColor}
                    flexDirection="row"
                    key={`${start + i}:${item.text}:${item.display}:${item.meta ?? ''}`}
                    width="100%"
                  >
                    <Box flexShrink={0} width={nameW}>
                      <Text bold color={theme.color.label}>
                        {' '}
                        {item.display}
                      </Text>
                    </Box>
                    {item.meta ? (
                      // Descriptions in the neutral gray, NOT a gold-family
                      // tone — label vs muted are near-twins on some skins,
                      // which made command and description read as one run.
                      // Active row: meta rides the chip, so it uses row ink.
                      <Text backgroundColor={row.backgroundColor} color={active ? row.color : theme.color.statusFg}>
                        {item.meta}
                      </Text>
                    ) : null}
                  </Box>
                )
              })
            })()}
          </Box>
        </FloatBox>
      )
    })
  }

  return (
    <Box alignItems="flex-start" bottom="100%" flexDirection="column" left={0} position="absolute" right={0}>
      <WidgetGrid cols={cols} columns={1} gap={0} paddingX={0} paddingY={0} rowGap={0} widgets={widgets} />
    </Box>
  )
}
