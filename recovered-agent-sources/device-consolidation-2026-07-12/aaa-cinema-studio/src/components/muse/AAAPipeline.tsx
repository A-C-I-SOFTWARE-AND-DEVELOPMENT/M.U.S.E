'use client'

import * as React from 'react'
import {
  Workflow,
  Lightbulb,
  Hammer,
  Layers,
  FlaskConical,
  Gauge,
  Award,
  Rocket,
  CheckCircle2,
  Circle,
  AlertTriangle,
  ArrowRight,
  Plus,
} from 'lucide-react'
import { useMuse, type ModuleId } from '@/lib/store'
import {
  ModuleHeader,
  Panel,
  PanelHeader,
  Tag,
  useFetch,
  EmptyState,
  GenerateButton,
} from './shared'
import { PhaseRail, type PhaseState } from './PhaseRail'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

// The canonical AAA milestone gates — Concept → Prototype → Vertical Slice →
// Alpha → Beta → Gold → Launch. Mirrors the M.U.S.E repo's PhaseRail config.
const MILESTONES = [
  { id: 'concept', label: 'Concept', icon: Lightbulb, module: 'narrative' as ModuleId },
  { id: 'prototype', label: 'Prototype', icon: Hammer, module: 'world' as ModuleId },
  { id: 'vertical', label: 'Vertical Slice', icon: Layers, module: 'cinematographer' as ModuleId },
  { id: 'alpha', label: 'Alpha', icon: FlaskConical, module: 'characters' as ModuleId },
  { id: 'beta', label: 'Beta', icon: Gauge, module: 'vault' as ModuleId },
  { id: 'gold', label: 'Gold', icon: Award, module: 'director' as ModuleId },
  { id: 'launch', label: 'Launch', icon: Rocket, module: 'director' as ModuleId },
]

// Production health — derives a synthetic milestone state from project content counts.
function derivePhaseState(
  counts: { characters: number; scenes: number; scripts: number; assets: number; voiceTakes: number },
  milestoneIndex: number,
): PhaseState {
  // Very rough heuristic: each milestone needs a threshold of accumulated content.
  const total = counts.characters + counts.scenes + counts.scripts + counts.assets + counts.voiceTakes
  const thresholds = [0, 2, 6, 12, 20, 30, 40]
  if (total >= thresholds[milestoneIndex + 1] ?? 999) return 'done'
  if (total >= thresholds[milestoneIndex]) return 'current'
  return 'pending'
}

function deriveOverall(
  counts: { characters: number; scenes: number; scripts: number; assets: number; voiceTakes: number },
): { state: PhaseState[]; currentIndex: number } {
  const total = counts.characters + counts.scenes + counts.scripts + counts.assets + counts.voiceTakes
  const thresholds = [0, 2, 6, 12, 20, 30, 40, 99]
  let currentIndex = 0
  for (let i = 0; i < thresholds.length - 1; i++) {
    if (total >= thresholds[i] && total < thresholds[i + 1]) {
      currentIndex = i
      break
    }
    if (total >= thresholds[thresholds.length - 1]) currentIndex = thresholds.length - 2
  }
  const states: PhaseState[] = MILESTONES.map((_, i) => {
    if (i < currentIndex) return 'done'
    if (i === currentIndex) return 'current'
    return 'pending'
  })
  return { state: states, currentIndex }
}

function HealthBar({ label, value, max, color }: { label: string; value: number; max: number; color: string }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-[11px] font-mono">
        <span className="text-muted-foreground uppercase tracking-wider">{label}</span>
        <span className="text-foreground">{value}</span>
      </div>
      <div className="h-1.5 rounded-full bg-muted/40 overflow-hidden">
        <div className={cn('h-full rounded-full transition-all', color)} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

export function AAAPipeline() {
  const { activeProject, setModule } = useMuse()
  const { data: project, loading } = useFetch<any>(
    activeProject ? `/api/projects/${activeProject.id}` : null,
    [activeProject?.id],
  )

  if (!activeProject) {
    return (
      <div>
        <ModuleHeader
          index="★"
          title="AAA Pipeline"
          subtitle="Milestone gates from Concept to Gold to Launch — the studio pipeline, tracked."
          icon={Workflow}
        />
        <Panel className="p-0">
          <EmptyState
            icon={Workflow}
            title="No production selected"
            desc="Greenlight a production to track its journey through the AAA milestone gates."
            action={<Button className="bg-white text-[#04060c] hover:bg-white/90 gap-2" onClick={() => setModule('mission')}><ArrowRight className="h-4 w-4" /> Go to Mission Control</Button>}
          />
        </Panel>
      </div>
    )
  }

  const counts = project?._count ?? { characters: 0, scenes: 0, scripts: 0, assets: 0, voiceTakes: 0 }
  const fullCounts = {
    characters: project?.characters?.length ?? counts.characters ?? 0,
    scenes: project?.scenes?.length ?? counts.scenes ?? 0,
    scripts: project?.scripts?.length ?? counts.scripts ?? 0,
    assets: project?.assets?.length ?? counts.assets ?? 0,
    voiceTakes: project?.voiceTakes?.length ?? counts.voiceTakes ?? 0,
  }
  const { state, currentIndex } = deriveOverall(fullCounts)
  const currentMilestone = MILESTONES[currentIndex]
  const overallPct = Math.round(((currentIndex) / (MILESTONES.length - 1)) * 100)

  return (
    <div className="space-y-6">
      <ModuleHeader
        index="★"
        title="AAA Pipeline"
        subtitle="Milestone gates from Concept to Gold to Launch — the studio pipeline, tracked end to end."
        icon={Workflow}
      />

      {/* Overall progress hero */}
      <Panel spotlight className="p-6 md:p-8">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <Tag tone="spectral">{activeProject.genre || 'Untitled'}</Tag>
              <Tag tone="muted">{activeProject.medium}</Tag>
              <Tag tone="core">PIPELINE ACTIVE</Tag>
            </div>
            <h2 className="font-display text-2xl md:text-3xl font-semibold text-foreground">{activeProject.title}</h2>
            <p className="text-sm text-muted-foreground mt-1">
              Current gate: <span className="text-[#7ae0ff] font-medium">{currentMilestone?.label}</span>
            </p>
          </div>
          <div className="text-right">
            <div className="font-display text-4xl font-bold spectral-text">{overallPct}%</div>
            <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">to launch</div>
          </div>
        </div>
        <div className="mt-5">
          <PhaseRail
            phases={MILESTONES.map((m, i) => ({ id: m.id, label: m.label, state: state[i] }))}
          />
        </div>
      </Panel>

      {/* Milestone detail grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {MILESTONES.map((m, i) => {
          const Icon = m.icon
          const st = state[i]
          return (
            <Panel key={m.id} className={cn('p-5 transition-colors', st === 'current' && 'spectral-edge-left')}>
              <div className="flex items-start justify-between mb-3">
                <div className={cn(
                  'flex h-10 w-10 items-center justify-center rounded-md border',
                  st === 'done' && 'border-[#7ae0ff]/40 bg-[#7ae0ff]/10 text-[#7ae0ff]',
                  st === 'current' && 'border-white/40 bg-white/10 text-white',
                  st === 'pending' && 'border-border bg-muted/20 text-muted-foreground',
                )}>
                  <Icon className="h-5 w-5" />
                </div>
                {st === 'done' && <CheckCircle2 className="h-4 w-4 text-[#7ae0ff]" />}
                {st === 'current' && <span className="rec-dot h-2 w-2 rounded-full core-dot" />}
                {st === 'pending' && <Circle className="h-4 w-4 text-muted-foreground/40" />}
              </div>
              <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground/70 mb-1">
                Gate {String(i + 1).padStart(2, '0')}
              </div>
              <h3 className="font-display text-base font-semibold text-foreground">{m.label}</h3>
              <p className="text-xs text-muted-foreground mt-1">
                {st === 'done' && 'Cleared. Artefacts archived to the vault.'}
                {st === 'current' && 'In progress. Drive this gate to completion.'}
                {st === 'pending' && 'Awaiting prior gates.'}
              </p>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setModule(m.module)}
                className={cn(
                  'mt-3 h-7 px-2 text-xs gap-1',
                  st === 'current' ? 'text-[#7ae0ff] hover:text-[#7ae0ff]' : 'text-muted-foreground hover:text-foreground',
                )}
              >
                Open {m.label === 'Launch' ? "Director's Cut" : m.label === 'Gold' ? "Director's Cut" : m.label + ' tools'}
                <ArrowRight className="h-3 w-3" />
              </Button>
            </Panel>
          )
        })}
      </div>

      {/* Production health */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Panel className="p-0">
          <PanelHeader title="Production Health" desc="Asset coverage across the pipeline." right={<Tag tone="spectral">LIVE</Tag>} />
          <div className="p-5 space-y-4">
            <HealthBar label="Characters" value={fullCounts.characters} max={8} color="bg-[#7ae0ff]" />
            <HealthBar label="Scenes / Storyboard" value={fullCounts.scenes} max={24} color="bg-[#b388ff]" />
            <HealthBar label="Scripts / Narrative" value={fullCounts.scripts} max={16} color="bg-[#5b8cff]" />
            <HealthBar label="Visual Assets" value={fullCounts.assets} max={40} color="bg-[#5be3a0]" />
            <HealthBar label="Voice Takes" value={fullCounts.voiceTakes} max={20} color="bg-[#f5c451]" />
          </div>
        </Panel>

        <Panel className="p-0">
          <PanelHeader title="Next Actions" desc="Recommended moves to advance the current gate." />
          <div className="p-5 space-y-2">
            {currentIndex < MILESTONES.length - 1 && (
              <>
                <div className="flex items-start gap-3 rounded-md border border-border/70 bg-muted/20 p-3">
                  <AlertTriangle className="h-4 w-4 text-[#f5c451] mt-0.5 shrink-0" />
                  <div className="text-sm">
                    <span className="text-foreground font-medium">Advance to {MILESTONES[currentIndex + 1]?.label}.</span>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      Produce more assets in the current gate's tools to clear <span className="text-[#7ae0ff]">{currentMilestone?.label}</span>.
                    </p>
                  </div>
                </div>
                <Button
                  onClick={() => setModule(currentMilestone.module)}
                  className="w-full bg-white text-[#04060c] hover:bg-white/90 gap-2"
                >
                  <Plus className="h-4 w-4" /> Open {currentMilestone.label} tools
                </Button>
              </>
            )}
            {currentIndex >= MILESTONES.length - 1 && (
              <div className="flex items-start gap-3 rounded-md border border-[#7ae0ff]/40 bg-[#7ae0ff]/5 p-3">
                <Rocket className="h-4 w-4 text-[#7ae0ff] mt-0.5 shrink-0" />
                <div className="text-sm">
                  <span className="text-foreground font-medium">Launch-ready.</span>
                  <p className="text-xs text-muted-foreground mt-0.5">All milestone gates cleared. Open the Director's Cut to assemble the final reel.</p>
                </div>
              </div>
            )}
          </div>
        </Panel>
      </div>
    </div>
  )
}
