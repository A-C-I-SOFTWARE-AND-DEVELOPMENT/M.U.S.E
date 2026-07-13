'use client'

import * as React from 'react'
import {
  LayoutDashboard,
  ScrollText,
  Drama,
  Clapperboard,
  Globe2,
  Mic2,
  ScanEye,
  Images,
  Film,
  Sparkles,
  ArrowRight,
  Cpu,
  Aperture,
  AudioLines,
  Palette,
  Wand2,
} from 'lucide-react'
import { useMuse, type ModuleId } from '@/lib/store'
import {
  ModuleHeader,
  Panel,
  PanelHeader,
  Tag,
  useFetch,
  EmptyState,
  Loader,
} from './shared'
import { PhaseRail } from './PhaseRail'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { MuseProject } from '@/lib/types'

const QUICK: { id: ModuleId; label: string; icon: any; blurb: string }[] = [
  { id: 'narrative', label: 'Write a Scene', icon: ScrollText, blurb: 'Industry-format screenplay' },
  { id: 'characters', label: 'Forge a Character', icon: Drama, blurb: 'Portrait + dossier' },
  { id: 'cinematographer', label: 'Board a Shot', icon: Clapperboard, blurb: 'Frame-by-frame' },
  { id: 'world', label: 'Build the World', icon: Globe2, blurb: 'Lore, factions, palette' },
  { id: 'voice', label: 'Perform a Line', icon: Mic2, blurb: 'Voice acting on demand' },
  { id: 'vision', label: 'Read a Frame', icon: ScanEye, blurb: 'Reverse-engineer reference' },
]

const ENGINES = [
  { icon: Cpu, name: 'Narrative Engine', desc: 'Flagship LLM dramaturgy — beat sheets, branching nodes, title sequences, gameplay loops, level & boss design, cinematography & score briefs.', tag: 'TEXT' },
  { icon: Aperture, name: 'Cinematic Imager', desc: 'Generative frames tuned to shot type, lens & palette — AAA key-art quality.', tag: 'IMAGE' },
  { icon: AudioLines, name: 'Voice Stage', desc: 'Directed voice acting for live performance capture.', tag: 'AUDIO' },
  { icon: ScanEye, name: 'Vision Lab', desc: 'VLM reads any reference into a production brief.', tag: 'VISION' },
  { icon: Palette, name: 'World Architect', desc: 'Cosmology, geography, factions & conflict engines.', tag: 'WORLD' },
  { icon: Wand2, name: 'AAA Pipeline', desc: 'Milestone gates — Concept → Prototype → Vertical Slice → Alpha → Beta → Gold → Launch.', tag: 'PIPELINE' },
]

function StatCard({ label, value, icon: Icon, onClick }: { label: string; value: number; icon: any; onClick?: () => void }) {
  return (
    <button
      onClick={onClick}
      className="tonal-card rounded-xl p-4 text-left hover:border-[#7ae0ff]/40 transition-colors group"
    >
      <div className="flex items-center justify-between">
        <Icon className="h-4 w-4 text-muted-foreground group-hover:text-[#7ae0ff] transition-colors" />
        <span className="font-mono text-[10px] text-muted-foreground/60 uppercase tracking-wider">{label}</span>
      </div>
      <div className="mt-3 font-display text-3xl font-bold text-foreground">{value}</div>
      <div className="mt-1 flex items-center gap-1 text-[11px] text-[#7ae0ff]/0 group-hover:text-[#7ae0ff]/80 transition-colors">
        <span>open</span> <ArrowRight className="h-3 w-3" />
      </div>
    </button>
  )
}

export function MissionControl() {
  const { activeProject, setModule } = useMuse()
  const { data: project, loading } = useFetch<any>(
    activeProject ? `/api/projects/${activeProject.id}` : null,
    [activeProject?.id],
  )
  const { data: stats } = useFetch<any>('/api/vault', [])

  if (!activeProject) {
    return (
      <div>
        <ModuleHeader
          index="01"
          title="Mission Control"
          subtitle="Command deck for your productions."
          icon={LayoutDashboard}
        />
        <Panel className="p-0">
          <EmptyState
            icon={Film}
            title="No production selected"
            desc="Greenlight your first production to begin. M.U.S.E will carry it from logline to final cut."
            action={
              <Button className="bg-white text-[#04060c] hover:bg-white/90 gap-2" onClick={() => setModule('narrative')}>
                <Sparkles className="h-4 w-4" /> Start Writing
              </Button>
            }
          />
        </Panel>
      </div>
    )
  }

  const counts = project?._count ?? activeProject._count ?? { characters: 0, scenes: 0, scripts: 0, assets: 0, voiceTakes: 0 }

  return (
    <div className="space-y-6">
      <ModuleHeader
        index="00"
        title="Mission Control"
        subtitle="Command deck — every module, one stage."
        icon={LayoutDashboard}
      />

      {/* Hero */}
      <Panel spotlight className="p-6 md:p-8">
        <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2 mb-2">
              <Tag tone="spectral">{activeProject.genre || 'Untitled Genre'}</Tag>
              <Tag tone="muted">{activeProject.medium}</Tag>
              {activeProject.palette && <Tag tone="violet">PALETTE LOCKED</Tag>}
            </div>
            <h2 className="font-display text-3xl md:text-4xl font-bold text-foreground leading-tight">
              {activeProject.title}
            </h2>
            <p className="mt-2 text-muted-foreground max-w-2xl text-sm md:text-base">
              {activeProject.logline || 'No logline yet — draft one in the Narrative Engine.'}
            </p>
            {activeProject.palette && (
              <p className="mt-2 text-xs text-muted-foreground/80 font-mono">
                ▚ {activeProject.palette}
              </p>
            )}
          </div>
          <div className="flex items-center gap-2 font-mono text-[10px] text-muted-foreground/70 uppercase tracking-cinematic">
            <span className="rec-dot h-1.5 w-1.5 rounded-full core-dot" /> In Production
          </div>
        </div>
      </Panel>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <StatCard label="Characters" value={counts.characters ?? 0} icon={Drama} onClick={() => setModule('characters')} />
        <StatCard label="Scenes" value={counts.scenes ?? 0} icon={Clapperboard} onClick={() => setModule('cinematographer')} />
        <StatCard label="Scripts" value={counts.scripts ?? 0} icon={ScrollText} onClick={() => setModule('narrative')} />
        <StatCard label="Assets" value={counts.assets ?? 0} icon={Images} onClick={() => setModule('vault')} />
        <StatCard label="Voice Takes" value={counts.voiceTakes ?? 0} icon={Mic2} onClick={() => setModule('voice')} />
      </div>

      {/* Pipeline snapshot */}
      <Panel spotlight className="p-5">
        <div className="flex items-center justify-between mb-3">
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground/70">AAA Pipeline</span>
              <Tag tone="spectral">MILESTONE GATES</Tag>
            </div>
            <h3 className="font-display text-base font-semibold text-foreground mt-1">Concept → Prototype → Vertical Slice → Alpha → Beta → Gold → Launch</h3>
          </div>
          <Button variant="ghost" size="sm" className="text-[#7ae0ff] hover:text-[#7ae0ff] gap-1" onClick={() => setModule('pipeline')}>Open Pipeline <ArrowRight className="h-3.5 w-3.5" /></Button>
        </div>
        <PhaseRail
          phases={[
            { id: 'concept', label: 'Concept', state: (counts.scripts ?? 0) > 0 ? 'done' : 'current' },
            { id: 'prototype', label: 'Prototype', state: (counts.scripts ?? 0) > 0 && (counts.characters ?? 0) === 0 ? 'current' : (counts.characters ?? 0) > 0 ? 'done' : 'pending' },
            { id: 'vertical', label: 'Vertical Slice', state: (counts.scenes ?? 0) > 0 ? 'done' : (counts.characters ?? 0) > 0 ? 'current' : 'pending' },
            { id: 'alpha', label: 'Alpha', state: (counts.assets ?? 0) >= 4 ? 'done' : (counts.scenes ?? 0) > 0 ? 'current' : 'pending' },
            { id: 'beta', label: 'Beta', state: (counts.voiceTakes ?? 0) > 0 ? 'done' : (counts.assets ?? 0) >= 4 ? 'current' : 'pending' },
            { id: 'gold', label: 'Gold', state: 'pending' },
            { id: 'launch', label: 'Launch', state: 'pending' },
          ]}
        />
      </Panel>

      {/* Quick actions */}
      <Panel className="p-0">
        <PanelHeader title="Quick Actions" desc="Jump straight into the creative work." />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-px bg-border/40">
          {QUICK.map((q) => {
            const Icon = q.icon
            return (
              <button
                key={q.id}
                onClick={() => setModule(q.id)}
                className="bg-card/40 hover:bg-[#7ae0ff]/5 p-5 text-left transition-colors group"
              >
                <div className="flex items-start gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-md border border-border bg-muted/30 group-hover:border-[#7ae0ff]/40 group-hover:text-[#7ae0ff] transition-colors">
                    <Icon className="h-5 w-5" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <span className="font-display text-sm font-semibold text-foreground">{q.label}</span>
                      <ArrowRight className="h-3.5 w-3.5 text-muted-foreground group-hover:text-[#7ae0ff] group-hover:translate-x-0.5 transition-all" />
                    </div>
                    <p className="text-xs text-muted-foreground mt-0.5">{q.blurb}</p>
                  </div>
                </div>
              </button>
            )
          })}
        </div>
      </Panel>

      {/* Engine capabilities */}
      <Panel className="p-0">
        <PanelHeader
          title="The M.U.S.E Harness"
          desc="Six interlocking engines. One unbroken creative pipeline from premise to premiere."
          right={<Tag tone="gold">STATE OF THE ART</Tag>}
        />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-px bg-border/40">
          {ENGINES.map((e) => {
            const Icon = e.icon
            return (
              <div key={e.name} className="bg-card/40 p-5">
                <div className="flex items-center gap-2 mb-2">
                  <Icon className="h-4 w-4 text-gold" />
                  <span className="font-display text-sm font-semibold text-foreground">{e.name}</span>
                  <span className="ml-auto"><Tag tone="muted">{e.tag}</Tag></span>
                </div>
                <p className="text-xs text-muted-foreground leading-relaxed">{e.desc}</p>
              </div>
            )
          })}
        </div>
      </Panel>

      {/* Recent assets strip */}
      {project?.assets?.length > 0 && (
        <Panel className="p-0">
          <PanelHeader
            title="Recent Frames"
            desc="Latest imagery from the vault."
            right={<Button variant="ghost" size="sm" className="text-gold hover:text-gold" onClick={() => setModule('vault')}>Open Vault <ArrowRight className="h-3.5 w-3.5 ml-1" /></Button>}
          />
          <div className="p-4 grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
            {project.assets.slice(0, 6).map((a: any) => (
              <div key={a.id} className="relative aspect-video overflow-hidden rounded border border-border">
                <div className="film-edge absolute top-0 inset-x-0 h-1.5 opacity-50" />
                <div className="film-edge absolute bottom-0 inset-x-0 h-1.5 opacity-50" />
                { }
                <img src={a.imageUrl} alt={a.title} className="h-full w-full object-cover" />
              </div>
            ))}
          </div>
        </Panel>
      )}

      {/* Global ledger */}
      {stats && (
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-[11px] font-mono text-muted-foreground/70 uppercase tracking-wider px-1">
          <span>Ledger:</span>
          <span>{stats.projects} productions</span>
          <span className="text-border">·</span>
          <span>{stats.characters} characters</span>
          <span className="text-border">·</span>
          <span>{stats.scenes} scenes</span>
          <span className="text-border">·</span>
          <span>{stats.assets} assets</span>
          <span className="text-border">·</span>
          <span>{stats.voiceTakes} voice takes</span>
        </div>
      )}
    </div>
  )
}
