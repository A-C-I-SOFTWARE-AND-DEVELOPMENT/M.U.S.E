'use client'

import * as React from 'react'
import dynamic from 'next/dynamic'
import { Canvas } from '@react-three/fiber'
import {
  Boxes,
  Play,
  Pause,
  ChevronLeft,
  ChevronRight,
  Grid3x3,
  Users,
  RotateCw,
  CloudFog,
  Maximize2,
  RefreshCw,
} from 'lucide-react'
import { useMuse } from '@/lib/store'
import {
  ModuleHeader,
  Panel,
  PanelHeader,
  EmptyState,
  Tag,
  useFetch,
} from './shared'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { Slider } from '@/components/ui/slider'
import { toast } from 'sonner'

// The R3F scene contents — loaded only client-side.
const SandboxScene = dynamic(
  () => import('./sandbox/SandboxScene').then((m) => m.SandboxScene),
  { ssr: false, loading: () => null },
)

interface Frame {
  url: string
  title?: string
}

export function Sandbox() {
  const { activeProject, setModule } = useMuse()
  const { data: project } = useFetch<any>(
    activeProject ? `/api/projects/${activeProject.id}` : null,
    [activeProject?.id],
  )

  // Reel = scenes' image URLs, falling back to assets.
  const reel: Frame[] = React.useMemo(() => {
    const scenes = (project?.scenes ?? []).filter((s: any) => s.imageUrl)
    if (scenes.length) return scenes.map((s: any) => ({ url: s.imageUrl, title: s.title }))
    const assets = (project?.assets ?? []).filter((a: any) => a.imageUrl)
    return assets.map((a: any) => ({ url: a.imageUrl, title: a.title }))
  }, [project])

  const portraits = React.useMemo(() => {
    return (project?.characters ?? [])
      .filter((c: any) => c.portraitUrl)
      .map((c: any) => ({ url: c.portraitUrl, name: c.name }))
  }, [project])

  const [frame, setFrame] = React.useState(0)
  const [playing, setPlaying] = React.useState(false)
  const [showGrid, setShowGrid] = React.useState(true)
  const [showPortraits, setShowPortraits] = React.useState(true)
  const [autoRotate, setAutoRotate] = React.useState(false)
  const [fog, setFog] = React.useState(0.3)

  // Reset frame when reel changes.
  React.useEffect(() => {
    setFrame(0)
  }, [activeProject?.id])

  // Auto-advance the reel while playing.
  React.useEffect(() => {
    if (!playing || reel.length === 0) return
    const id = setInterval(() => {
      setFrame((f) => (f + 1) % reel.length)
    }, 3000)
    return () => clearInterval(id)
  }, [playing, reel.length])

  function fullscreen() {
    const el = document.getElementById('sandbox-canvas-wrap')
    if (!el) return
    if (document.fullscreenElement) {
      document.exitFullscreen().catch(() => {})
    } else {
      el.requestFullscreen().catch(() => toast.error('Fullscreen unavailable'))
    }
  }

  if (!activeProject) {
    return (
      <div>
        <ModuleHeader
          index="11"
          title="Sandbox"
          subtitle="A real-time 3D preview studio — stage and watch your creations come alive."
          icon={Boxes}
        />
        <Panel className="p-0">
          <EmptyState
            icon={Boxes}
            title="No production selected"
            desc="Select a production to stage its scenes, characters and assets in the 3D preview studio."
            action={
              <Button className="bg-white text-[#04060c] hover:bg-white/90 gap-2" onClick={() => setModule('mission')}>
                Go to Mission Control
              </Button>
            }
          />
        </Panel>
      </div>
    )
  }

  const total = reel.length
  const currentTitle = reel[frame]?.title ?? `Frame ${frame + 1}`

  return (
    <div className="space-y-6">
      <ModuleHeader
        index="11"
        title="Sandbox"
        subtitle="A real-time 3D preview studio — stage your scenes on the cinema screen, arc your cast around it, and orbit the stage."
        icon={Boxes}
      />

      {/* 3D viewport */}
      <Panel className="p-0 overflow-hidden">
        <PanelHeader
          title="Preview Stage"
          desc={`${activeProject.title} · ${total} frames · ${portraits.length} cast`}
          right={
            <div className="flex items-center gap-1.5">
              <Tag tone="spectral">WEBGL</Tag>
              <Tag tone="muted">RT RENDER</Tag>
              <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-foreground" onClick={fullscreen}>
                <Maximize2 className="h-4 w-4" />
              </Button>
            </div>
          }
        />
        <div
          id="sandbox-canvas-wrap"
          className="relative bg-black"
          style={{ height: 'min(62vh, 560px)' }}
        >
          <Canvas
            camera={{ position: [0, 4, 16], fov: 45, near: 0.1, far: 100 }}
            gl={{ antialias: true, toneMapping: 2, toneMappingExposure: 1.1 }}
            dpr={[1, 2]}
          >
            <color attach="background" args={['#050507']} />
            <SandboxScene
              reelImages={reel.map((r) => r.url)}
              portraits={portraits}
              frame={frame}
              showGrid={showGrid}
              showPortraits={showPortraits}
              autoRotate={autoRotate}
              fog={fog}
            />
          </Canvas>

          {/* HUD overlay — frame info */}
          {total > 0 && (
            <div className="absolute top-3 left-3 flex items-center gap-2 glass-strong rounded-md px-3 py-1.5">
              <span className="rec-dot h-1.5 w-1.5 rounded-full core-dot" />
              <span className="font-mono text-[10px] uppercase tracking-wider text-white">
                FRAME {String(frame + 1).padStart(2, '0')} / {String(total).padStart(2, '0')}
              </span>
            </div>
          )}

          {/* HUD overlay — hint */}
          <div className="absolute bottom-3 right-3 font-mono text-[10px] uppercase tracking-wider text-muted-foreground/60 glass rounded px-2 py-1">
            drag to orbit · scroll to zoom
          </div>

          {/* Empty overlay */}
          {total === 0 && portraits.length === 0 && (
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
              <div className="text-center">
                <Boxes className="h-10 w-10 text-muted-foreground/30 mx-auto mb-3" />
                <p className="text-sm text-muted-foreground">The stage is empty.</p>
                <p className="text-xs text-muted-foreground/60 mt-1">
                  Generate scenes, characters or assets to populate the reel.
                </p>
              </div>
            </div>
          )}
        </div>
      </Panel>

      {/* Control deck */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Transport */}
        <Panel className="p-0 lg:col-span-2">
          <PanelHeader title="Transport" desc="Play the reel across the cinema screen." right={playing ? <Tag tone="core">PLAYING</Tag> : <Tag tone="muted">PAUSED</Tag>} />
          <div className="p-5">
            <div className="flex items-center gap-3">
              <Button
                variant="outline"
                size="icon"
                className="h-10 w-10 border-border text-foreground hover:bg-muted/40 bg-transparent"
                onClick={() => setFrame((f) => (f - 1 + total) % Math.max(total, 1))}
                disabled={total === 0}
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <Button
                onClick={() => setPlaying((p) => !p)}
                disabled={total === 0}
                className="h-12 w-12 rounded-full bg-white text-[#04060c] hover:bg-white/90 p-0"
              >
                {playing ? <Pause className="h-5 w-5" /> : <Play className="h-5 w-5 ml-0.5" />}
              </Button>
              <Button
                variant="outline"
                size="icon"
                className="h-10 w-10 border-border text-foreground hover:bg-muted/40 bg-transparent"
                onClick={() => setFrame((f) => (f + 1) % Math.max(total, 1))}
                disabled={total === 0}
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
              <div className="flex-1 min-w-0 ml-2">
                <p className="text-sm text-foreground truncate font-medium">{currentTitle}</p>
                <p className="text-[11px] text-muted-foreground font-mono">
                  {total > 0 ? `${frame + 1} of ${total}` : 'no frames'}
                </p>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setFrame(0)}
                disabled={total === 0}
                className="text-muted-foreground hover:text-foreground gap-1.5"
              >
                <RefreshCw className="h-3.5 w-3.5" /> Reset
              </Button>
            </div>
            {/* Scrubber */}
            {total > 0 && (
              <div className="mt-4">
                <Slider
                  value={[frame]}
                  min={0}
                  max={Math.max(total - 1, 0)}
                  step={1}
                  onValueChange={(v) => setFrame(v[0])}
                  className="cursor-pointer"
                />
                <div className="flex justify-between mt-1 font-mono text-[9px] text-muted-foreground/60">
                  <span>01</span>
                  <span>{String(total).padStart(2, '0')}</span>
                </div>
              </div>
            )}
          </div>
        </Panel>

        {/* Stage controls */}
        <Panel className="p-0">
          <PanelHeader title="Stage" desc="Environment & camera." />
          <div className="p-5 space-y-4">
            <ToggleRow icon={Grid3x3} label="Grid floor" value={showGrid} onChange={setShowGrid} />
            <ToggleRow icon={Users} label="Cast arc" value={showPortraits} onChange={setShowPortraits} />
            <ToggleRow icon={RotateCw} label="Auto-orbit" value={autoRotate} onChange={setAutoRotate} />
            <div className="space-y-1.5">
              <div className="flex items-center gap-2">
                <CloudFog className="h-3.5 w-3.5 text-muted-foreground" />
                <span className="text-xs uppercase tracking-wider text-muted-foreground">Atmospheric fog</span>
                <span className="ml-auto font-mono text-[10px] text-muted-foreground/70">{Math.round(fog * 100)}%</span>
              </div>
              <Slider
                value={[fog]}
                min={0}
                max={1}
                step={0.05}
                onValueChange={(v) => setFog(v[0])}
              />
            </div>
          </div>
        </Panel>
      </div>

      {/* Status footer */}
      <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-[11px] font-mono text-muted-foreground/70 uppercase tracking-wider px-1">
        <span>Sandbox</span>
        <span className="text-border">·</span>
        <span>{reel.length} reel frames</span>
        <span className="text-border">·</span>
        <span>{portraits.length} cast members</span>
        <span className="text-border">·</span>
        <span className="text-[#7ae0ff]">WebGL 2 · Three.js</span>
      </div>
    </div>
  )
}

function ToggleRow({
  icon: Icon,
  label,
  value,
  onChange,
}: {
  icon: React.ComponentType<{ className?: string }>
  label: string
  value: boolean
  onChange: (v: boolean) => void
}) {
  return (
    <div className="flex items-center gap-2">
      <Icon className="h-3.5 w-3.5 text-muted-foreground" />
      <span className="text-xs uppercase tracking-wider text-muted-foreground flex-1">{label}</span>
      <Switch
        checked={value}
        onCheckedChange={onChange}
        className="data-[state=checked]:bg-[#7ae0ff] data-[state=unchecked]:bg-muted"
      />
    </div>
  )
}
