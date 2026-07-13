'use client'

import * as React from 'react'
import { Gamepad2, Aperture, Layers, Sparkles, Trash2 } from 'lucide-react'
import { useMuse } from '@/lib/store'
import {
  ModuleHeader,
  Panel,
  PanelHeader,
  Field,
  GenerateButton,
  ImageFrame,
  useFetch,
  EmptyState,
  Tag,
  Loader,
  copyToClipboard,
} from './shared'
import { EraTabs } from './PlatformSelector'
import { Textarea } from '@/components/ui/textarea'
import { Button } from '@/components/ui/button'
import { toast } from 'sonner'
import {
  PLATFORMS,
  platformsByEra,
  getPlatform,
  type Era,
} from '@/lib/platforms'
import { cn } from '@/lib/utils'

interface CellState {
  imageUrl?: string
  loading: boolean
  error?: string
}

const SAMPLE_CONCEPTS = [
  'a lone wanderer overlooking a ruined neon city at dusk',
  'a knight confronting a dragon in a cathedral of bone',
  'a cyberpunk samurai on a rain-soaked Tokyo street',
  'a space marine breaching an alien hive',
  'a sorceress summoning a storm over a cracked desert',
]

export function FidelityLab() {
  const { activeProject } = useMuse()
  const [concept, setConcept] = React.useState(SAMPLE_CONCEPTS[0])
  const [era, setEra] = React.useState<Era>('engine')
  const [cells, setCells] = React.useState<Record<string, CellState>>({})
  const [batching, setBatching] = React.useState(false)

  const eraPlatforms = platformsByEra(era)

  async function generateOne(platformId: string) {
    if (!concept.trim()) {
      toast.error('Enter a concept first')
      return
    }
    setCells((c) => ({ ...c, [platformId]: { loading: true } }))
    try {
      const res = await fetch('/api/generate-image', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: concept,
          size: '1344x768',
          type: 'concept',
          title: `${concept.slice(0, 40)} — ${getPlatform(platformId)?.label}`,
          projectId: activeProject?.id ?? null,
          save: true,
          platform: platformId,
        }),
      })
      const json = await res.json()
      if (!json.ok) throw new Error(json.error || 'Generation failed')
      setCells((c) => ({
        ...c,
        [platformId]: { loading: false, imageUrl: json.data.imageUrl },
      }))
    } catch (e: any) {
      setCells((c) => ({
        ...c,
        [platformId]: { loading: false, error: e?.message || 'Failed' },
      }))
      toast.error(`${getPlatform(platformId)?.label}: ${e?.message || 'failed'}`)
    }
  }

  async function generateEra() {
    if (!concept.trim()) {
      toast.error('Enter a concept first')
      return
    }
    setBatching(true)
    // Sequential to be kind to the API; each card shows its own loading state.
    for (const p of eraPlatforms) {
      await generateOne(p.id)
    }
    setBatching(false)
    toast.success(`Generated ${eraPlatforms.length} platform variants`)
  }

  function clearAll() {
    setCells({})
  }

  const generatedCount = Object.values(cells).filter((c) => c.imageUrl).length

  return (
    <div className="space-y-6">
      <ModuleHeader
        index="★"
        title="Fidelity Lab"
        subtitle="One concept, every console generation. Render the same scene from Game Boy to PS5 and watch the medium's visual evolution in real time."
        icon={Gamepad2}
      />

      {/* Concept composer */}
      <Panel className="p-0">
        <PanelHeader
          title="Concept"
          desc="The subject rendered across every platform. Be specific and visual."
          right={
            generatedCount > 0 ? (
              <Button variant="ghost" size="sm" onClick={clearAll} className="text-muted-foreground hover:text-foreground h-8 gap-1">
                <Trash2 className="h-3.5 w-3.5" /> Clear grid
              </Button>
            ) : null
          }
        />
        <div className="p-5 space-y-4">
          <Textarea
            value={concept}
            onChange={(e) => setConcept(e.target.value)}
            placeholder="e.g. a lone wanderer overlooking a ruined neon city at dusk"
            rows={2}
            className="resize-none bg-background/60 text-sm"
          />
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground/70 mr-1">Samples:</span>
            {SAMPLE_CONCEPTS.map((s, i) => (
              <button
                key={i}
                onClick={() => setConcept(s)}
                className="rounded border border-border px-2 py-1 text-[10px] text-muted-foreground hover:text-foreground hover:border-[#7ae0ff]/40 transition-colors truncate max-w-[180px]"
              >
                {s.slice(0, 32)}…
              </button>
            ))}
          </div>
        </div>
      </Panel>

      {/* Era selector */}
      <Panel spotlight className="p-5">
        <div className="flex items-center justify-between gap-4 flex-wrap mb-4">
          <div className="flex items-center gap-2">
            <Layers className="h-4 w-4 text-[#7ae0ff]" />
            <span className="font-display text-sm font-semibold text-foreground">Console Generation</span>
            <Tag tone="spectral">{eraPlatforms.length} platforms</Tag>
          </div>
          <GenerateButton
            loading={batching}
            onClick={generateEra}
            icon={Sparkles}
            className="gap-2"
          >
            Render entire era
          </GenerateButton>
        </div>
        <EraTabs value={era} onChange={setEra} />
        <p className="text-xs text-muted-foreground mt-3">
          {ERAS_DESC[era]}
        </p>
      </Panel>

      {/* Platform grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {eraPlatforms.map((p) => {
          const cell = cells[p.id]
          return (
            <Panel key={p.id} className={cn('p-0 overflow-hidden', cell?.imageUrl && 'spectral-edge-left')}>
              <div className="flex items-center gap-2.5 px-4 py-3 border-b border-border/60">
                <span
                  className="h-3 w-3 rounded-sm shrink-0 border border-white/10"
                  style={{ background: p.accent }}
                />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-foreground truncate">{p.label}</span>
                    <span className="font-mono text-[10px] text-muted-foreground/70">{p.code}</span>
                  </div>
                  <div className="text-[10px] text-muted-foreground/60">{p.maker} · {p.year}</div>
                </div>
                {cell?.imageUrl && <Tag tone="spectral">RENDERED</Tag>}
              </div>
              <div className="p-3">
                <ImageFrame
                  src={cell?.imageUrl}
                  alt={`${p.label} render of ${concept}`}
                  loading={cell?.loading}
                  aspect="aspect-video"
                  caption={cell?.error ? `⚠ ${cell.error}` : undefined}
                />
                <div className="flex items-center gap-2 mt-3">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => generateOne(p.id)}
                    disabled={cell?.loading}
                    className="gap-1.5 h-8 border-[#7ae0ff]/40 text-[#7ae0ff] hover:bg-[#7ae0ff]/10 hover:text-[#7ae0ff] bg-transparent text-xs"
                  >
                    <Aperture className="h-3.5 w-3.5" />
                    {cell?.imageUrl ? 'Re-render' : 'Render'}
                  </Button>
                  {cell?.imageUrl && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => copyToClipboard(cell.imageUrl!, 'Image data URL copied')}
                      className="text-muted-foreground hover:text-foreground h-8 text-xs"
                    >
                      Copy
                    </Button>
                  )}
                  <span className="ml-auto font-mono text-[9px] text-muted-foreground/50 uppercase tracking-wider truncate max-w-[80px]">
                    {p.era}
                  </span>
                </div>
              </div>
            </Panel>
          )
        })}
      </div>

      {/* Empty hint */}
      {generatedCount === 0 && !batching && (
        <Panel className="p-0">
          <EmptyState
            icon={Gamepad2}
            title="No renders yet"
            desc="Pick a concept, choose a console generation, and render a single platform or the entire era. The same subject will be re-imagined through each platform's distinct visual signature."
            action={
              <Button className="bg-white text-[#04060c] hover:bg-white/90 gap-2" onClick={generateEra}>
                <Sparkles className="h-4 w-4" /> Render {platformsByEra(era).length} platforms
              </Button>
            }
          />
        </Panel>
      )}

      {activeProject && (
        <div className="text-[11px] font-mono text-muted-foreground/60 uppercase tracking-wider px-1">
          Renders save to the Asset Vault under project: <span className="text-[#7ae0ff]">{activeProject.title}</span>
        </div>
      )}
    </div>
  )
}

const ERAS_DESC: Record<Era, string> = {
  engine: 'Unreal Engine 5 fidelity — Lumen dynamic global illumination, Nanite virtualized geometry, hardware path tracing, Megascans photoreal materials. The rendering ceiling, through prompts.',
  pixel: 'Handhelds and 8/16-bit sprite work — strict limited palettes, dithering, crunchy pixels, CRT screens. Game Boy, NES, SNES.',
  '32bit': 'The birth of 3D — affine texture warping, jittery vertices, distance fog, vertex lighting. PS1, N64.',
  '128bit': 'Sixth generation — clean low-poly, interlaced SD, glossy specular, baked lighting. PS2, GameCube, Xbox.',
  hd: 'The HD revolution — bloom, HDR, SSAO, motion blur, deferred rendering. PS3, Xbox 360, Wii.',
  modern: 'Physically based rendering — PBR materials, screen-space reflections, color grading. PS4, Xbox One, Switch.',
  current: 'Ray-traced realism — RT reflections, RT global illumination, volumetrics, 4K. PS5, Xbox Series X, PC Ultra.',
}
