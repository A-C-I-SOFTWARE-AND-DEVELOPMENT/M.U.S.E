'use client'

import * as React from 'react'
import {
  Images,
  Sparkles,
  Trash2,
  Expand,
  Copy,
  Clapperboard,
  Drama,
  Mic2,
  Image as ImageIcon,
} from 'lucide-react'
import { useMuse } from '@/lib/store'
import {
  ModuleHeader,
  Panel,
  PanelHeader,
  Field,
  GenerateButton,
  ImageFrame,
  useGenerate,
  useFetch,
  EmptyState,
  Tag,
  Loader,
  copyToClipboard,
} from './shared'
import { PlatformSelector } from './PlatformSelector'
import { Input } from '@/components/ui/input'
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
  DialogDescription,
} from '@/components/ui/dialog'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import type { MuseAsset } from '@/lib/types'

const TYPES = ['concept', 'environment', 'portrait', 'storyboard', 'prop'] as const
const ASPECTS = [
  { value: '1344x768', label: '1344x768 WIDE' },
  { value: '768x1344', label: '768x1344 PORTRAIT' },
  { value: '1024x1024', label: '1024x1024 SQUARE' },
  { value: '1440x720', label: '1440x720 CINEMASCOPE' },
] as const

function StatTile({
  label,
  value,
  icon: Icon,
}: {
  label: string
  value: number
  icon: React.ComponentType<{ className?: string }>
}) {
  return (
    <div className="panel p-3">
      <div className="flex items-center justify-between">
        <Icon className="h-3.5 w-3.5 text-gold/70" />
        <span className="font-mono text-[9px] text-muted-foreground/60 uppercase tracking-wider">
          {label}
        </span>
      </div>
      <div className="mt-2 font-display text-2xl font-bold text-foreground tabular-nums">
        {value}
      </div>
    </div>
  )
}

export function AssetVault() {
  const { activeProject } = useMuse()
  const [prompt, setPrompt] = React.useState('')
  const [type, setType] = React.useState<string>('concept')
  const [size, setSize] = React.useState<string>('1344x768')
  const [filter, setFilter] = React.useState<string>('all')
  const [expanded, setExpanded] = React.useState<MuseAsset | null>(null)
  const [platform, setPlatform] = React.useState<string | undefined>(undefined)

  const gen = useGenerate<{ imageUrl: string; asset: MuseAsset }>('/api/generate-image')
  const assetsUrl = activeProject ? `/api/assets?projectId=${activeProject.id}` : null
  const { data: assets, loading: assetsLoading, reload: reloadAssets } = useFetch<MuseAsset[]>(
    assetsUrl,
    [activeProject?.id],
  )
  const { data: stats, reload: reloadStats } = useFetch<any>('/api/vault', [activeProject?.id])

  React.useEffect(() => {
    setPrompt('')
    setType('concept')
    setSize('1344x768')
    setFilter('all')
    setExpanded(null)
  }, [activeProject?.id])

  async function forge() {
    if (!activeProject) return toast.error('Select a production first')
    if (!prompt.trim()) return toast.error('Enter a prompt first')
    const data = await gen.run(
      {
        prompt,
        size,
        type,
        title: prompt.slice(0, 60),
        projectId: activeProject.id,
        save: true,
        platform,
      },
      { successMsg: 'Asset forged', errorMsg: 'Imager stalled' },
    )
    if (data) {
      setPrompt('')
      reloadAssets()
      reloadStats()
    }
  }

  async function deleteAsset(id: string) {
    try {
      const res = await fetch(`/api/assets?id=${id}`, { method: 'DELETE' })
      const json = await res.json()
      if (!json.ok) throw new Error(json.error)
      toast.success('Asset removed')
      reloadAssets()
      reloadStats()
      setExpanded((prev) => (prev?.id === id ? null : prev))
    } catch (e: any) {
      toast.error(e?.message || 'Delete failed')
    }
  }

  const filtered = (assets ?? []).filter((a) => filter === 'all' || a.type === filter)

  return (
    <div className="space-y-6">
      <ModuleHeader
        index="08"
        title="Asset Vault"
        subtitle="The generative library — forge frames on demand and curate the visual canon of your production."
        icon={Images}
      />

      {!activeProject ? (
        <Panel className="p-0">
          <EmptyState
            icon={Images}
            title="Select a production"
            desc="Choose or greenlight a production to open its vault."
          />
        </Panel>
      ) : (
        <>
          {/* Forge panel */}
          <Panel className="p-0">
            <PanelHeader
              title="Forge to Vault"
              desc="Quick-generate an asset and commit it directly to the canon."
              right={<Tag tone="spectral">{activeProject.title}</Tag>}
            />
            <div className="p-5">
              <div className="flex flex-col md:flex-row gap-3 md:items-end">
                <div className="flex-1">
                  <Field label="Prompt" hint="cinematic · specific">
                    <Input
                      value={prompt}
                      onChange={(e) => setPrompt(e.target.value)}
                      placeholder="e.g. neon-drenched alley, rain-slicked pavement, lone figure silhouette…"
                      className="bg-background/60"
                      onKeyDown={(e) => {
                        if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') forge()
                      }}
                    />
                  </Field>
                </div>
                <div className="w-full md:w-44">
                  <Field label="Type">
                    <Select value={type} onValueChange={setType}>
                      <SelectTrigger className="bg-background/60 w-full">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {TYPES.map((t) => (
                          <SelectItem key={t} value={t}>
                            {t}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </Field>
                </div>
                <div className="w-full md:w-52">
                  <Field label="Aspect">
                    <Select value={size} onValueChange={setSize}>
                      <SelectTrigger className="bg-background/60 w-full">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {ASPECTS.map((a) => (
                          <SelectItem key={a.value} value={a.value}>
                            {a.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </Field>
                </div>
                <GenerateButton
                  loading={gen.loading}
                  onClick={forge}
                  disabled={!prompt.trim()}
                  icon={Sparkles}
                  className="shrink-0"
                >
                  Forge
                </GenerateButton>
                <PlatformSelector value={platform} onChange={setPlatform} />
              </div>
            </div>
          </Panel>

          {/* Stats strip */}
          {stats && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <StatTile label="Total Assets" value={stats.assets ?? 0} icon={Images} />
              <StatTile label="Scenes" value={stats.scenes ?? 0} icon={Clapperboard} />
              <StatTile label="Characters" value={stats.characters ?? 0} icon={Drama} />
              <StatTile label="Voice Takes" value={stats.voiceTakes ?? 0} icon={Mic2} />
            </div>
          )}

          {/* Gallery */}
          <Panel className="p-0">
            <PanelHeader
              title="The Vault"
              desc={`${filtered.length} asset${filtered.length === 1 ? '' : 's'} curated`}
              right={
                <div className="flex flex-wrap items-center gap-1">
                  {(['all', ...TYPES] as const).map((t) => (
                    <button
                      key={t}
                      onClick={() => setFilter(t)}
                      className={cn(
                        'rounded-sm px-2 py-1 text-[10px] font-mono uppercase tracking-wider border transition-colors',
                        filter === t
                          ? 'border-gold/40 bg-gold/10 text-gold'
                          : 'border-border bg-transparent text-muted-foreground hover:text-foreground hover:border-border/80',
                      )}
                    >
                      {t}
                    </button>
                  ))}
                </div>
              }
            />
            <div className="max-h-[640px] overflow-y-auto scrollbar-muse p-4">
              {assetsLoading ? (
                <div className="p-6">
                  <Loader label="Loading vault" />
                </div>
              ) : filtered.length === 0 ? (
                <EmptyState
                  icon={ImageIcon}
                  title="Vault is empty"
                  desc="Forge an asset above to begin curating the visual canon."
                />
              ) : (
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
                  {filtered.map((a) => {
                    const isPortrait = a.type === 'portrait'
                    return (
                      <div key={a.id} className="group relative">
                        <ImageFrame
                          src={a.imageUrl}
                          alt={a.title}
                          aspect={isPortrait ? 'aspect-square' : 'aspect-video'}
                          caption={a.title}
                        />
                        <span className="absolute top-2 left-2 z-10">
                          <Tag tone="crimson">{a.type}</Tag>
                        </span>
                        <div className="absolute top-2 right-2 z-10 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                          <button
                            onClick={() => setExpanded(a)}
                            className="glass-strong rounded-md p-1.5 text-foreground/90 hover:text-gold transition-colors"
                            aria-label="Expand asset"
                            title="Expand"
                          >
                            <Expand className="h-3.5 w-3.5" />
                          </button>
                          <button
                            onClick={() => deleteAsset(a.id)}
                            className="glass-strong rounded-md p-1.5 text-foreground/90 hover:text-crimson transition-colors"
                            aria-label="Delete asset"
                            title="Delete"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          </Panel>
        </>
      )}

      {/* Expand dialog */}
      <Dialog open={!!expanded} onOpenChange={(o) => !o && setExpanded(null)}>
        <DialogContent className="sm:max-w-3xl bg-card border-border">
          {expanded && (
            <>
              <DialogHeader>
                <DialogTitle className="font-display text-lg text-foreground">
                  {expanded.title}
                </DialogTitle>
                <DialogDescription className="flex items-center gap-2">
                  <Tag tone="crimson">{expanded.type}</Tag>
                  <span className="font-mono text-[10px] text-muted-foreground/60 uppercase tracking-wider">
                    {new Date(expanded.createdAt).toLocaleString()}
                  </span>
                </DialogDescription>
              </DialogHeader>
              <div className="relative overflow-hidden rounded-md border border-border bg-black aspect-video">
                <div className="film-edge absolute top-0 inset-x-0 h-2 opacity-60 z-10" />
                <div className="film-edge absolute bottom-0 inset-x-0 h-2 opacity-60 z-10" />
                { }
                <img
                  src={expanded.imageUrl}
                  alt={expanded.title}
                  className="h-full w-full object-contain"
                />
              </div>
              <div className="rounded-md border border-border bg-background/60 p-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-mono text-[10px] text-muted-foreground uppercase tracking-wider">
                    Prompt
                  </span>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 text-gold hover:text-gold gap-1"
                    onClick={() => copyToClipboard(expanded.prompt, 'Prompt copied')}
                  >
                    <Copy className="h-3 w-3" /> Copy
                  </Button>
                </div>
                <p className="text-xs text-foreground/80 font-mono leading-relaxed whitespace-pre-wrap break-words">
                  {expanded.prompt}
                </p>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
