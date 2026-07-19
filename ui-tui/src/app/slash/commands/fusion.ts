import type { FusionDepth, FusionSetParams, FusionStatus } from '../../../gatewayTypes.js'
import { rpcErrorMessage } from '../../../lib/rpc.js'
import type { PanelSection } from '../../../types.js'
import { applyFusionAvailability } from '../../agentModeStore.js'
import { patchOverlayState } from '../../overlayStore.js'
import type { SlashCommand, SlashRunCtx } from '../types.js'

const DEPTHS: readonly FusionDepth[] = ['skip', 'light', 'standard', 'deep', 'adaptive']

const USAGE = 'usage: /fusion [on|off|depth <skip|light|standard|deep|adaptive>|rounds <1-5>|moa on|off|status]'

const summarize = (r: FusionStatus) => {
  const moa = r.moa ?? {}

  return [
    r.enabled ? 'on' : 'off',
    `depth ${String(r.depth ?? '?').toUpperCase()}`,
    `rounds ≤${r.rounds_planned ?? '?'}`,
    `moa ${moa.enabled ? 'on' : 'off'}`
  ].join(' · ')
}

const showStatus = (ctx: SlashRunCtx) => {
  ctx.gateway
    .rpc<FusionStatus>('fusion.status', {})
    .then(
      ctx.guarded<FusionStatus>(r => {
        if (!r) {
          return ctx.transcript.sys('◈ fusion: empty response from gateway')
        }

        applyFusionAvailability(r)

        const moa = r.moa ?? {}
        const router = r.model_router ?? []

        const sections: PanelSection[] = [
          {
            rows: [
              ['Fusion', r.enabled ? 'on' : 'off'],
              ['Depth', String(r.depth ?? '?').toUpperCase()],
              ['Rounds', `${r.current_round ?? 0}/${r.rounds_planned ?? '?'}`],
              ['Role', String(r.role ?? '—').toUpperCase()],
              ['LTI α', typeof r.lti_alpha === 'number' ? r.lti_alpha.toFixed(3) : '—'],
              ['MOA', `${moa.enabled ? 'on' : 'off'} · OPENROUTER key ${moa.key_present ? 'present' : 'missing'}`]
            ]
          }
        ]

        if (router.length) {
          sections.push({
            rows: router
              .slice(0, 7)
              .map(m => [
                String(m.model ?? '?'),
                `${m.specialty ?? ''} · bias ${Number(m.ema_bias ?? 0).toFixed(2)} · ${m.calls ?? 0} calls`
              ]),
            title: 'Model router'
          })
        }

        ctx.transcript.panel('◈ Fusion / MOA', sections)
      })
    )
    .catch((e: unknown) => {
      if (ctx.stale()) {
        return
      }

      ctx.transcript.sys(`◈ fusion unavailable — requires newer gateway (${rpcErrorMessage(e)})`)
    })
}

const applySet = (ctx: SlashRunCtx, params: FusionSetParams) => {
  ctx.gateway
    .rpc<FusionStatus>('fusion.set', { ...params })
    .then(
      ctx.guarded<FusionStatus>(r => {
        if (r) {
          applyFusionAvailability(r)
          ctx.transcript.sys(`◈ fusion · ${summarize(r)}`)
        } else {
          ctx.transcript.sys('◈ fusion.set applied (empty status response)')
        }
      })
    )
    .catch((e: unknown) => {
      if (ctx.stale()) {
        return
      }

      ctx.transcript.sys(`◈ fusion unavailable — requires newer gateway (${rpcErrorMessage(e)})`)
    })
}

export const fusionCommands: SlashCommand[] = [
  {
    help: 'fusion/MOA center · /fusion [on|off|depth <d>|rounds <n>|moa on|off|status]',
    name: 'fusion',
    run: (arg, ctx) => {
      const text = arg.trim()

      // Bare /fusion → fullscreen overlay (design.md 1.3B).
      if (!text) {
        patchOverlayState({ fusion: true })

        return
      }

      const [sub = '', ...rest] = text.split(/\s+/).filter(Boolean)
      const value = rest.join(' ').trim().toLowerCase()

      switch (sub.toLowerCase()) {
        case 'on':
          return applySet(ctx, { enabled: true })

        case 'off':
          return applySet(ctx, { enabled: false })
        case 'depth': {
          const depth = value as FusionDepth

          if (!DEPTHS.includes(depth)) {
            return ctx.transcript.sys(USAGE)
          }

          return applySet(ctx, { depth })
        }

        case 'rounds': {
          const n = parseInt(value, 10)

          if (!Number.isFinite(n) || n < 1 || n > 5) {
            return ctx.transcript.sys('usage: /fusion rounds <1-5>')
          }

          return applySet(ctx, { rounds_cap: n })
        }

        case 'moa': {
          if (value !== 'on' && value !== 'off') {
            return ctx.transcript.sys('usage: /fusion moa on|off')
          }

          return applySet(ctx, { moa: value === 'on' })
        }

        case 'status':
          return showStatus(ctx)

        default:
          return ctx.transcript.sys(USAGE)
      }
    },
    usage: '[on|off|depth <d>|rounds <n>|moa on|off|status]'
  }
]
