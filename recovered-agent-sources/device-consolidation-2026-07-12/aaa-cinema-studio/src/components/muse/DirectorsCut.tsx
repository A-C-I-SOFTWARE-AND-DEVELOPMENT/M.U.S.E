'use client'

import * as React from 'react'
import {
  Film,
  Play,
  Pause,
  ChevronLeft,
  ChevronRight,
  Mic2,
  Drama,
  ScrollText,
  VolumeX,
  Clapperboard,
} from 'lucide-react'
import { useMuse } from '@/lib/store'
import {
  ModuleHeader,
  Panel,
  PanelHeader,
  Tag,
  EmptyState,
  Markdown,
  GenerateButton,
  useFetch,
  Loader,
} from './shared'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Collapsible,
  CollapsibleTrigger,
  CollapsibleContent,
} from '@/components/ui/collapsible'
import { cn } from '@/lib/utils'
import { VOICES } from '@/lib/types'
import type { MuseScene, MuseCharacter, MuseVoiceTake, MuseScript } from '@/lib/types'

interface FullProject {
  id: string
  title: string
  logline: string
  genre: string
  medium: string
  palette: string
  scenes: MuseScene[]
  characters: MuseCharacter[]
  voiceTakes: MuseVoiceTake[]
  scripts: MuseScript[]
}

function formatTimecode(totalSeconds: number, frame: number): string {
  const h = Math.floor(totalSeconds / 3600)
  const m = Math.floor((totalSeconds % 3600) / 60)
  const s = Math.floor(totalSeconds % 60)
  const ff = Math.floor(frame % 24)
  return [h, m, s, ff].map((n) => String(n).padStart(2, '0')).join(':')
}

function voiceLabel(id: string): string {
  return VOICES.find((v) => v.id === id)?.label ?? id
}

function ScriptRoll({ scripts }: { scripts: MuseScript[] }) {
  const [openId, setOpenId] = React.useState<string | null>(null)
  if (!scripts || scripts.length === 0) {
    return (
      <EmptyState
        icon={ScrollText}
        title="No scripts"
        desc="Draft scenes & dialogue in the Narrative Engine."
      />
    )
  }
  return (
    <div className="space-y-2">
      {scripts.map((sc) => {
        const open = openId === sc.id
        const excerpt =
          sc.content
            .replace(/[#>*`_-]/g, '')
            .replace(/\s+/g, ' ')
            .trim()
            .slice(0, 200) || '—'
        return (
          <Collapsible key={sc.id} open={open} onOpenChange={(o) => setOpenId(o ? sc.id : null)}>
            <div
              className={cn(
                'rounded-md border bg-card/40 transition-colors',
                open ? 'border-gold/30' : 'border-border/70',
              )}
            >
              <CollapsibleTrigger asChild>
                <button className="w-full text-left p-3 flex items-center gap-3">
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded border border-border bg-muted/30">
                    <ScrollText className="h-4 w-4 text-gold/80" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-display text-sm font-semibold text-foreground truncate">
                        {sc.title}
                      </span>
                      {sc.act && <Tag tone="muted">{sc.act}</Tag>}
                      {sc.kind && <Tag tone="gold">{sc.kind}</Tag>}
                    </div>
                    <p className="text-[11px] text-muted-foreground/70 mt-0.5 line-clamp-2">
                      {excerpt}
                    </p>
                  </div>
                  <ChevronRight
                    className={cn(
                      'h-4 w-4 text-muted-foreground transition-transform shrink-0',
                      open && 'rotate-90',
                    )}
                  />
                </button>
              </CollapsibleTrigger>
              <CollapsibleContent>
                <div className="border-t border-border/60 p-4">
                  <Markdown content={sc.content} />
                </div>
              </CollapsibleContent>
            </div>
          </Collapsible>
        )
      })}
    </div>
  )
}

function VoiceCue({ takes }: { takes: MuseVoiceTake[] }) {
  const [selectedId, setSelectedId] = React.useState<string>(takes[0]?.id ?? '')

  React.useEffect(() => {
    if (takes.length && !takes.find((t) => t.id === selectedId)) {
      setSelectedId(takes[0].id)
    }
  }, [takes, selectedId])

  const selected = takes.find((t) => t.id === selectedId) ?? takes[0]
  const audioSrc = selected?.audioBase64 ?? ''

  return (
    <div className="space-y-3">
      <div className="flex flex-col sm:flex-row gap-3 sm:items-end">
        <div className="flex-1">
          <label className="text-xs uppercase tracking-wider text-muted-foreground block mb-1.5">
            Cue — {selected ? voiceLabel(selected.voice) : '—'}
          </label>
          <Select value={selectedId} onValueChange={setSelectedId}>
            <SelectTrigger className="bg-background/60 w-full">
              <SelectValue placeholder="Select a take" />
            </SelectTrigger>
            <SelectContent>
              {takes.map((t) => (
                <SelectItem key={t.id} value={t.id}>
                  {voiceLabel(t.voice)} · {t.text.slice(0, 40)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex items-center gap-2 text-muted-foreground">
          <Mic2 className="h-4 w-4 text-gold/70" />
          <span className="font-mono text-[10px] uppercase tracking-wider">
            {takes.length} takes available
          </span>
        </div>
      </div>
      {audioSrc ? (
        <audio controls src={audioSrc} className="w-full h-10" />
      ) : (
        <p className="text-xs text-muted-foreground/70 italic">No audio attached to this take.</p>
      )}
      {selected?.text && (
        <p className="text-xs text-muted-foreground/80 italic border-l-2 border-gold/40 pl-3">
          &ldquo;{selected.text.slice(0, 200)}
          {selected.text.length > 200 ? '…' : ''}&rdquo;
        </p>
      )}
    </div>
  )
}

export function DirectorsCut() {
  const { activeProject, setModule } = useMuse()
  const projectUrl = activeProject ? `/api/projects/${activeProject.id}` : null
  const { data: project, loading } = useFetch<FullProject>(projectUrl, [activeProject?.id])

  const scenes = React.useMemo(() => {
    const s = project?.scenes ?? []
    return [...s].sort((a, b) => (a.sequence ?? 0) - (b.sequence ?? 0))
  }, [project?.scenes])
  const total = scenes.length

  const [currentFrame, setCurrentFrame] = React.useState(0)
  const [playing, setPlaying] = React.useState(false)

  // Reset on project switch
  React.useEffect(() => {
    setCurrentFrame(0)
    setPlaying(false)
  }, [activeProject?.id])

  // Clamp currentFrame when scenes change
  React.useEffect(() => {
    if (total === 0) {
      if (currentFrame !== 0) setCurrentFrame(0)
      return
    }
    if (currentFrame >= total) setCurrentFrame(total - 1)
  }, [total, currentFrame])

  // Pause if project unmounts / loading
  React.useEffect(() => {
    if (loading) setPlaying(false)
  }, [loading])

  // Auto-advance loop (3.2s per frame)
  React.useEffect(() => {
    if (!playing || total === 0) return
    const t = setTimeout(() => {
      setCurrentFrame((f) => (f + 1) % total)
    }, 3200)
    return () => clearTimeout(t)
  }, [playing, currentFrame, total])

  const currentScene = total > 0 ? scenes[currentFrame] : null
  const timecode = formatTimecode(currentFrame * 5, currentFrame)
  const progress = total > 0 ? ((currentFrame + 1) / total) * 100 : 0

  if (!activeProject) {
    return (
      <div className="space-y-6">
        <ModuleHeader
          index="09"
          title="Director's Cut"
          subtitle="The assembly reel — where scenes, voices & frames become one."
          icon={Film}
        />
        <Panel className="p-0">
          <EmptyState
            icon={Film}
            title="No production selected"
            desc="Choose or greenlight a production to assemble its reel."
            action={
              <Button
                className="bg-gold text-primary-foreground hover:bg-gold/90 gap-2"
                onClick={() => setModule('mission')}
              >
                <Clapperboard className="h-4 w-4" /> Go to Mission Control
              </Button>
            }
          />
        </Panel>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <ModuleHeader
        index="09"
        title="Director's Cut"
        subtitle="The assembly reel — where scenes, voices & frames become one."
        icon={Film}
      />

      {loading ? (
        <Panel className="p-6">
          <Loader label="Loading production" />
        </Panel>
      ) : !project ? (
        <Panel className="p-0">
          <EmptyState icon={Film} title="Production not found" desc="Try selecting another production." />
        </Panel>
      ) : (
        <>
          {/* 1. TITLE CARD */}
          <Panel spotlight className="p-6 md:p-8">
            <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
              <div className="min-w-0">
                <div className="flex items-center gap-2 mb-3 flex-wrap">
                  <Tag tone="gold">{project.genre || 'Untitled Genre'}</Tag>
                  <Tag tone="muted">{project.medium}</Tag>
                  {project.palette && <Tag tone="crimson">PALETTE LOCKED</Tag>}
                </div>
                <h2 className="font-display text-3xl md:text-5xl font-bold text-foreground leading-tight">
                  {project.title}
                </h2>
                <p className="mt-3 text-muted-foreground max-w-2xl text-sm md:text-base">
                  {project.logline || 'No logline yet — draft one in the Narrative Engine.'}
                </p>
                {project.palette && (
                  <p className="mt-2 text-xs text-muted-foreground/80 font-mono">
                    ▚ {project.palette}
                  </p>
                )}
              </div>
              <div className="flex flex-col items-start md:items-end gap-2 shrink-0">
                <div className="flex items-center gap-2 font-mono text-[10px] text-crimson uppercase tracking-cinematic">
                  <span className="rec-dot h-2 w-2 rounded-full bg-crimson" /> REC
                </div>
                <div className="font-mono text-base md:text-lg text-gold tabular-nums">
                  {timecode}
                </div>
                <div className="font-mono text-[10px] text-muted-foreground/60 uppercase tracking-wider">
                  TC · 24FPS
                </div>
              </div>
            </div>
          </Panel>

          {/* 2. CONTROL DECK */}
          <Panel className="p-0">
            <PanelHeader
              title="Control Deck"
              desc="Scrub the reel or play the assembled sequence."
              right={<Tag tone="gold">{total} FRAMES</Tag>}
            />
            <div className="p-5 space-y-4">
              <div className="flex flex-wrap items-center gap-2">
                {!playing ? (
                  <GenerateButton
                    onClick={() => total > 0 && setPlaying(true)}
                    disabled={total === 0}
                    icon={Play}
                  >
                    Play Reel
                  </GenerateButton>
                ) : (
                  <GenerateButton onClick={() => setPlaying(false)} icon={Pause} variant="outline">
                    Pause
                  </GenerateButton>
                )}
                <Button
                  variant="outline"
                  size="icon"
                  className="h-9 w-9 border-border text-muted-foreground hover:text-gold"
                  disabled={total === 0}
                  onClick={() => setCurrentFrame((f) => (f - 1 + total) % total)}
                  aria-label="Previous frame"
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                <Button
                  variant="outline"
                  size="icon"
                  className="h-9 w-9 border-border text-muted-foreground hover:text-gold"
                  disabled={total === 0}
                  onClick={() => setCurrentFrame((f) => (f + 1) % total)}
                  aria-label="Next frame"
                >
                  <ChevronRight className="h-4 w-4" />
                </Button>
                <div className="flex-1" />
                <span className="font-mono text-xs text-muted-foreground tabular-nums">
                  FRAME {String(total > 0 ? currentFrame + 1 : 0).padStart(2, '0')} /{' '}
                  {String(total).padStart(2, '0')}
                </span>
              </div>
              <Progress value={progress} className="h-1.5 bg-border" />
              {total === 0 && (
                <p className="text-xs text-muted-foreground italic">
                  Board scenes in the Cinematographer first.
                </p>
              )}
            </div>
          </Panel>

          {/* 3. THE REEL */}
          <Panel className="p-0">
            <PanelHeader
              title="The Reel"
              desc="Now showing."
              right={currentScene && <Tag tone="muted">SCENE {currentScene.sequence}</Tag>}
            />
            <div className="p-5">
              {currentScene ? (
                <div>
                  <div className="relative overflow-hidden rounded-md border border-border bg-black aspect-video">
                    <div className="film-edge absolute top-0 inset-x-0 h-2 opacity-60 z-10" />
                    <div className="film-edge absolute bottom-0 inset-x-0 h-2 opacity-60 z-10" />
                    {currentScene.imageUrl ? (
                       
                      <img
                        src={currentScene.imageUrl}
                        alt={currentScene.title}
                        className="h-full w-full object-cover"
                      />
                    ) : (
                      <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 text-muted-foreground">
                        <Film className="h-10 w-10 text-muted-foreground/40" />
                        <span className="font-display text-lg text-foreground/60">
                          {currentScene.title}
                        </span>
                        <span className="font-mono text-[10px] uppercase tracking-wider">
                          No frame exposed
                        </span>
                      </div>
                    )}
                    {/* top-left shotType */}
                    <div className="absolute top-3 left-3 z-20">
                      <Tag tone="gold">{currentScene.shotType || 'SHOT'}</Tag>
                    </div>
                    {/* top-right timecode */}
                    <div className="absolute top-3 right-3 z-20">
                      <div className="glass-strong rounded px-2 py-1 font-mono text-[11px] text-gold tabular-nums">
                        {timecode}
                      </div>
                    </div>
                    {/* bottom scene title + location */}
                    <div className="absolute bottom-4 left-3 right-3 z-20">
                      <div className="glass-strong rounded-md px-3 py-2">
                        <div className="font-display text-sm font-semibold text-foreground truncate">
                          {currentScene.title}
                        </div>
                        {currentScene.location && (
                          <div className="font-mono text-[10px] text-muted-foreground uppercase tracking-wider mt-0.5 truncate">
                            {currentScene.location}
                            {currentScene.timeOfDay ? ` · ${currentScene.timeOfDay}` : ''}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                  <p className="mt-4 text-center text-sm italic text-muted-foreground/90 max-w-2xl mx-auto leading-relaxed">
                    {currentScene.description || '—'}
                  </p>
                </div>
              ) : (
                <EmptyState
                  icon={Film}
                  title="No scenes in the reel"
                  desc="Board scenes in the Cinematographer to assemble the cut."
                />
              )}
            </div>
          </Panel>

          {/* 4. VOICE CUE */}
          <Panel className="p-0">
            <PanelHeader
              title="Voice Cue"
              desc="Optionally underscore the current frame with a performance."
              right={<Tag tone="muted">{project.voiceTakes?.length ?? 0} TAKES</Tag>}
            />
            <div className="p-5">
              {project.voiceTakes && project.voiceTakes.length > 0 ? (
                <VoiceCue takes={project.voiceTakes} />
              ) : (
                <div className="flex items-center gap-2 text-sm text-muted-foreground italic">
                  <VolumeX className="h-4 w-4" /> No voice takes — perform one in the Voice Stage.
                </div>
              )}
            </div>
          </Panel>

          {/* 5. CAST STRIP */}
          <Panel className="p-0">
            <PanelHeader
              title="Ensemble"
              desc="The committed cast."
              right={<Tag tone="muted">{project.characters?.length ?? 0}</Tag>}
            />
            <div className="p-5">
              {project.characters && project.characters.length > 0 ? (
                <div className="flex gap-3 overflow-x-auto scrollbar-muse pb-2">
                  {project.characters.map((c) => (
                    <div key={c.id} className="shrink-0 w-20">
                      <div className="h-16 w-12 mx-auto overflow-hidden rounded border border-border bg-black">
                        {c.portraitUrl ? (
                           
                          <img
                            src={c.portraitUrl}
                            alt={c.name}
                            className="h-full w-full object-cover"
                          />
                        ) : (
                          <div className="h-full w-full flex items-center justify-center">
                            <Drama className="h-4 w-4 text-muted-foreground/40" />
                          </div>
                        )}
                      </div>
                      <div className="mt-1.5 text-center">
                        <div className="text-[11px] font-semibold text-foreground truncate">
                          {c.name}
                        </div>
                        <div className="mt-0.5 flex justify-center">
                          <Tag tone="gold">{c.role}</Tag>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState
                  icon={Drama}
                  title="Cast is empty"
                  desc="Forge characters in the Character Forge to populate the ensemble."
                />
              )}
            </div>
          </Panel>

          {/* 6. SCRIPT ROLL */}
          <Panel className="p-0">
            <PanelHeader
              title="Shooting Script"
              desc="Expand any script to read the full text."
              right={<Tag tone="muted">{project.scripts?.length ?? 0}</Tag>}
            />
            <div className="p-5">
              <ScriptRoll scripts={project.scripts ?? []} />
            </div>
          </Panel>
        </>
      )}
    </div>
  )
}
