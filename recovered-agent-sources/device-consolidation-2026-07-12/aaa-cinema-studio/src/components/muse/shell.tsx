'use client'

import * as React from 'react'
import {
  LayoutDashboard,
  Workflow,
  ScrollText,
  Drama,
  Clapperboard,
  Globe2,
  Gamepad2,
  Mic2,
  ScanEye,
  Images,
  Film,
  Boxes,
  Radio,
  Plus,
  Clapperboard as Clap,
  ChevronRight,
} from 'lucide-react'
import { useMuse, type ModuleId } from '@/lib/store'
import { useFetch } from './shared'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import type { MuseProject } from '@/lib/types'
import { GENRES } from '@/lib/types'

import { Glyph } from './Glyph'
import { SacredGeometry } from './SacredGeometry'
import { MissionControl } from './MissionControl'
import { AAAPipeline } from './AAAPipeline'
import { NarrativeEngine } from './NarrativeEngine'
import { CharacterForge } from './CharacterForge'
import { Cinematographer } from './Cinematographer'
import { WorldArchitect } from './WorldArchitect'
import { VoiceStage } from './VoiceStage'
import { VisionLab } from './VisionLab'
import { AssetVault } from './AssetVault'
import { FidelityLab } from './FidelityLab'
import { Sandbox } from './Sandbox'
import { GatewayBridge } from './GatewayBridge'
import { DirectorsCut } from './DirectorsCut'

const NAV: {
  id: ModuleId
  label: string
  index: string
  icon: React.ComponentType<{ className?: string }>
  desc: string
}[] = [
  { id: 'mission', label: 'Mission Control', index: '00', icon: LayoutDashboard, desc: 'Production overview' },
  { id: 'pipeline', label: 'AAA Pipeline', index: '★', icon: Workflow, desc: 'Milestone gates' },
  { id: 'narrative', label: 'Narrative Engine', index: '02', icon: ScrollText, desc: 'Scripts & story' },
  { id: 'characters', label: 'Character Forge', index: '03', icon: Drama, desc: 'Cast & portraits' },
  { id: 'cinematographer', label: 'Cinematographer', index: '04', icon: Clapperboard, desc: 'Storyboard frames' },
  { id: 'world', label: 'World Architect', index: '05', icon: Globe2, desc: 'Worldbuilding' },
  { id: 'fidelity', label: 'Fidelity Lab', index: '06', icon: Gamepad2, desc: 'Console platform renders' },
  { id: 'voice', label: 'Voice Stage', index: '07', icon: Mic2, desc: 'Voice acting' },
  { id: 'vision', label: 'Vision Lab', index: '08', icon: ScanEye, desc: 'Reference analysis' },
  { id: 'vault', label: 'Asset Vault', index: '09', icon: Images, desc: 'Generated assets' },
  { id: 'director', label: "Director's Cut", index: '10', icon: Film, desc: 'Assemble the reel' },
  { id: 'sandbox', label: 'Sandbox', index: '11', icon: Boxes, desc: '3D preview studio' },
  { id: 'gateway', label: 'Gateway Bridge', index: '12', icon: Radio, desc: 'Connect to musehq.io' },
]

function Wordmark() {
  return (
    <div className="flex items-center gap-3">
      <div className="relative">
        <Glyph size={30} spin />
      </div>
      <div className="leading-none">
        <div className="font-display text-lg font-semibold tracking-wide text-foreground">
          muse
        </div>
        <div className="font-mono text-[9px] uppercase tracking-[0.6px] text-muted-foreground">
          Multi-Use Synaptic Entity
        </div>
      </div>
    </div>
  )
}

function NewProjectDialog({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean
  onOpenChange: (v: boolean) => void
  onCreated: (p: MuseProject) => void
}) {
  const [title, setTitle] = React.useState('')
  const [logline, setLogline] = React.useState('')
  const [genre, setGenre] = React.useState(GENRES[0])
  const [medium, setMedium] = React.useState<'film' | 'game' | 'hybrid'>('film')
  const [palette, setPalette] = React.useState('')
  const [loading, setLoading] = React.useState(false)

  async function create() {
    if (!title.trim()) {
      toast.error('Title required')
      return
    }
    setLoading(true)
    try {
      const res = await fetch('/api/projects', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, logline, genre, medium, palette }),
      })
      const json = await res.json()
      if (!json.ok) throw new Error(json.error)
      toast.success('Production greenlit')
      onCreated(json.data)
      setTitle('')
      setLogline('')
      setPalette('')
      onOpenChange(false)
    } catch (e: any) {
      toast.error(e?.message || 'Failed to create project')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="glass-strong border-border">
        <DialogHeader>
          <DialogTitle className="font-display flex items-center gap-2">
            <Clap className="h-4 w-4 text-gold" /> Greenlight a New Production
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <div className="space-y-1.5">
            <Label className="text-xs uppercase tracking-wider text-muted-foreground">Title</Label>
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. The Last Cartographer"
              className="bg-background/60"
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs uppercase tracking-wider text-muted-foreground">Logline</Label>
            <Textarea
              value={logline}
              onChange={(e) => setLogline(e.target.value)}
              placeholder="One sentence. The whole world in a breath."
              rows={2}
              className="resize-none bg-background/60"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label className="text-xs uppercase tracking-wider text-muted-foreground">Genre</Label>
              <Select value={genre} onValueChange={setGenre}>
                <SelectTrigger className="bg-background/60"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {GENRES.map((g) => (
                    <SelectItem key={g} value={g}>{g}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs uppercase tracking-wider text-muted-foreground">Medium</Label>
              <Select value={medium} onValueChange={(v: any) => setMedium(v)}>
                <SelectTrigger className="bg-background/60"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="film">Theatrical Film</SelectItem>
                  <SelectItem value="game">AAA Game</SelectItem>
                  <SelectItem value="hybrid">Hybrid</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs uppercase tracking-wider text-muted-foreground">Visual Palette (optional)</Label>
            <Input
              value={palette}
              onChange={(e) => setPalette(e.target.value)}
              placeholder="e.g. desaturated teal + ember orange, 35mm grain"
              className="bg-background/60"
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button onClick={create} disabled={loading} className="bg-white text-[#04060c] hover:bg-white/90 gap-2 font-semibold">
            {loading ? 'Greenlighting…' : 'Greenlight'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export function Shell() {
  const { activeModule, setModule, activeProject, setActiveProject, projects, setProjects, upsertProject } = useMuse()
  const [newOpen, setNewOpen] = React.useState(false)
  const { data, reload } = useFetch<MuseProject[]>('/api/projects', [])

  React.useEffect(() => {
    if (data) setProjects(data)
  }, [data, setProjects])

  React.useEffect(() => {
    if (data && data.length && !activeProject) {
      setActiveProject(data[0])
    }
  }, [data, activeProject, setActiveProject])

  const activeMeta = NAV.find((n) => n.id === activeModule)!

  return (
    <>
      <SacredGeometry width={520} height={480} className="sacred-geometry" />
      <div className="flex min-h-screen">
      {/* Sidebar — desktop */}
      <aside className="hidden lg:flex w-64 shrink-0 flex-col border-r border-border/70 bg-sidebar/60 backdrop-blur-sm">
        <div className="p-5 border-b border-border/60">
          <Wordmark />
        </div>
        <nav className="flex-1 overflow-y-auto scrollbar-muse p-3 space-y-1">
          <div className="px-2 py-2 font-mono text-[10px] uppercase tracking-cinematic text-muted-foreground/70">
            Production Modules
          </div>
          {NAV.map((item) => {
            const active = activeModule === item.id
            const Icon = item.icon
            return (
              <button
                key={item.id}
                onClick={() => setModule(item.id)}
                className={cn(
                  'group w-full flex items-center gap-3 rounded-md px-3 py-2.5 text-left transition-colors',
                  active
                    ? 'bg-[#0b0d12] spectral-edge-left'
                    : 'border border-transparent hover:bg-[#0b0d12]',
                )}
              >
                <div
                  className={cn(
                    'flex h-8 w-8 items-center justify-center rounded-md transition-colors',
                    active ? 'text-[#7ae0ff]' : 'text-muted-foreground group-hover:text-foreground',
                  )}
                >
                  <Icon className="h-4 w-4" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-[9px] text-muted-foreground/60">{item.index}</span>
                    <span className={cn('text-sm font-medium truncate', active ? 'text-white' : 'text-foreground')}>
                      {item.label}
                    </span>
                  </div>
                  <div className="text-[11px] text-muted-foreground/70 truncate">{item.desc}</div>
                </div>
                {active && <ChevronRight className="h-4 w-4 text-[#7ae0ff]/60" />}
              </button>
            )
          })}
        </nav>
        <div className="p-4 border-t border-border/60">
          <div className="flex items-center justify-between text-[10px] font-mono text-muted-foreground/70 uppercase tracking-wider">
            <span>Engine v1.0</span>
            <span className="flex items-center gap-1">
              <span className="rec-dot h-1.5 w-1.5 rounded-full bg-green-500/80" /> Online
            </span>
          </div>
        </div>
      </aside>

      {/* Main column */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <header className="sticky top-0 z-30 border-b border-border/70 bg-background/80 backdrop-blur-md">
          <div className="flex items-center gap-3 px-4 md:px-6 py-3">
            {/* mobile wordmark */}
            <div className="lg:hidden">
              <Wordmark />
            </div>
            <div className="hidden lg:flex items-center gap-2 text-xs text-muted-foreground">
              <span className="font-mono">{activeMeta.index}</span>
              <ChevronRight className="h-3 w-3" />
              <span className="text-foreground font-medium">{activeMeta.label}</span>
            </div>
            <div className="flex-1" />
            {/* Project switcher */}
            <Select
              value={activeProject?.id ?? ''}
              onValueChange={(v) => {
                const p = projects.find((x) => x.id === v)
                if (p) setActiveProject(p)
              }}
            >
              <SelectTrigger className="w-[200px] md:w-[280px] bg-card/60 border-border h-9">
                <SelectValue placeholder="No production selected" />
              </SelectTrigger>
              <SelectContent>
                {projects.length === 0 && (
                  <div className="px-3 py-2 text-xs text-muted-foreground">No productions yet</div>
                )}
                {projects.map((p) => (
                  <SelectItem key={p.id} value={p.id}>
                    <span className="truncate">{p.title}</span>
                    <span className="ml-2 text-[10px] text-muted-foreground uppercase">{p.medium}</span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button
              size="sm"
              onClick={() => setNewOpen(true)}
              className="gap-1.5 bg-white text-[#04060c] hover:bg-white/90 h-9 font-semibold"
            >
              <Plus className="h-4 w-4" /> <span className="hidden sm:inline">New</span>
            </Button>
          </div>
          {/* Mobile module nav */}
          <div className="lg:hidden border-t border-border/60 overflow-x-auto scrollbar-muse">
            <div className="flex gap-1 px-3 py-2 min-w-max">
              {NAV.map((item) => {
                const Icon = item.icon
                const active = activeModule === item.id
                return (
                  <button
                    key={item.id}
                    onClick={() => setModule(item.id)}
                    className={cn(
                      'flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs whitespace-nowrap border',
                      active ? 'bg-[#7ae0ff]/10 border-[#7ae0ff]/40 text-[#7ae0ff]' : 'border-transparent text-muted-foreground',
                    )}
                  >
                    <Icon className="h-3.5 w-3.5" />
                    {item.label}
                  </button>
                )
              })}
            </div>
          </div>
        </header>

        {/* Active module */}
        <main className="flex-1 px-4 md:px-6 lg:px-8 py-6 md:py-8 max-w-[1400px] w-full mx-auto fade-up" key={activeModule}>
          {activeModule === 'mission' && <MissionControl />}
          {activeModule === 'pipeline' && <AAAPipeline />}
          {activeModule === 'narrative' && <NarrativeEngine />}
          {activeModule === 'characters' && <CharacterForge />}
          {activeModule === 'cinematographer' && <Cinematographer />}
          {activeModule === 'world' && <WorldArchitect />}
          {activeModule === 'fidelity' && <FidelityLab />}
          {activeModule === 'voice' && <VoiceStage />}
          {activeModule === 'vision' && <VisionLab />}
          {activeModule === 'vault' && <AssetVault />}
          {activeModule === 'director' && <DirectorsCut />}
          {activeModule === 'sandbox' && <Sandbox />}
          {activeModule === 'gateway' && <GatewayBridge />}
        </main>

        {/* Sticky footer */}
        <footer className="mt-auto border-t border-border/70 bg-background/80 backdrop-blur-sm">
          <div className="px-4 md:px-6 lg:px-8 py-3 flex flex-col md:flex-row items-center justify-between gap-2 text-[11px] text-muted-foreground">
            <div className="flex items-center gap-2 font-mono uppercase tracking-wider">
              <span className="rec-dot h-1.5 w-1.5 rounded-full core-dot" />
              <span>muse — Multi-Use Synaptic Entity · the #1 AI harness for AAA games &amp; cinematic films</span>
            </div>
            <div className="flex items-center gap-3 font-mono">
              <a
                href="https://musehq.io"
                target="_blank"
                rel="noreferrer"
                className="text-[#7ae0ff] hover:text-white transition-colors"
              >
                musehq.io
              </a>
              <span className="text-border">·</span>
              <span>2.39:1 SCOPE</span>
              <span className="text-border">·</span>
              <span className="text-[#7ae0ff]">REC.709</span>
            </div>
          </div>
        </footer>
      </div>

      <NewProjectDialog
        open={newOpen}
        onOpenChange={setNewOpen}
        onCreated={(p) => {
          upsertProject(p)
          setActiveProject(p)
          reload()
        }}
      />
    </div>
    </>
  )
}
