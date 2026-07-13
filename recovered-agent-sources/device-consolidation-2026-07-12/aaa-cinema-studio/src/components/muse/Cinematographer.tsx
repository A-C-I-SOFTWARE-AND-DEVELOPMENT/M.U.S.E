'use client'

import * as React from 'react'
import {
  Clapperboard,
  Aperture,
  Save,
  Trash2,
  Clock,
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
  ApertureLoader,
} from './shared'
import { PlatformSelector } from './PlatformSelector'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { toast } from 'sonner'
import { SHOT_TYPES, ASPECT_BY_SHOT, type MuseScene } from '@/lib/types'

// Map an image size string to a Tailwind aspect class.
const ASPECT_CLASS: Record<string, string> = {
  '1440x720': 'aspect-video',
  '1344x768': 'aspect-video',
  '1024x1024': 'aspect-square',
  '768x1344': 'aspect-[3/4]',
  '720x1440': 'aspect-[3/4]',
}

function aspectFor(shotType: string): string {
  const size = ASPECT_BY_SHOT[shotType]
  return (size && ASPECT_CLASS[size]) || 'aspect-video'
}

function frameLabel(idx: number): string {
  return `FRAME ${String(idx + 1).padStart(2, '0')}`
}

export function Cinematographer() {
  const { activeProject } = useMuse()

  // Composer state
  const [title, setTitle] = React.useState('')
  const [sequence, setSequence] = React.useState('1')
  const [location, setLocation] = React.useState('')
  const [timeOfDay, setTimeOfDay] = React.useState('')
  const [mood, setMood] = React.useState('')
  const [shotType, setShotType] = React.useState(SHOT_TYPES[0])
  const [description, setDescription] = React.useState('')
  const [imageUrl, setImageUrl] = React.useState('')
  const [platform, setPlatform] = React.useState<string | undefined>(undefined)
  const [saving, setSaving] = React.useState(false)

  const img = useGenerate<{ imageUrl: string }>('/api/generate-image')

  const scenesUrl = activeProject ? `/api/scenes?projectId=${activeProject.id}` : null
  const { data: scenes, reload: reloadScenes, loading: scenesLoading } = useFetch<MuseScene[]>(
    scenesUrl,
    [activeProject?.id],
  )

  React.useEffect(() => {
    // Reset composer when production changes.
    setTitle(''); setSequence('1'); setLocation(''); setTimeOfDay(''); setMood('')
    setShotType(SHOT_TYPES[0]); setDescription(''); setImageUrl('')
  }, [activeProject?.id])

  function buildPrompt(): string {
    const parts = [
      'cinematic storyboard frame',
      `${shotType} shot`,
      location && location,
      timeOfDay && timeOfDay,
      mood && `mood: ${mood}`,
      description && description,
      activeProject?.genre && `${activeProject.genre} aesthetic`,
      activeProject?.palette && `palette: ${activeProject.palette}`,
      'anamorphic, volumetric light, 35mm film grain, color graded, ultra detailed, AAA cinematic, 2.39:1',
    ].filter(Boolean)
    return parts.join(', ')
  }

  async function exposeFrame() {
    if (!activeProject) return toast.error('Select a production first')
    if (!description.trim()) return toast.error('Describe the frame first')
    const prompt = buildPrompt()
    const size = ASPECT_BY_SHOT[shotType] ?? '1344x768'
    const data = await img.run(
      {
        prompt,
        size,
        type: 'storyboard',
        title: title || `${shotType} — ${location || 'Untitled'}`,
        projectId: activeProject.id,
        platform,
      },
      { successMsg: 'Frame exposed', errorMsg: 'Imager stalled' },
    )
    if (data?.imageUrl) setImageUrl(data.imageUrl)
  }

  async function commitToBoard() {
    if (!activeProject) return toast.error('Select a production first')
    if (!imageUrl) return toast.error('Expose a frame first')
    if (!title.trim()) return toast.error('Give the frame a title first')
    setSaving(true)
    try {
      const res = await fetch('/api/scenes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          projectId: activeProject.id,
          title,
          sequence: Number(sequence) || 0,
          slug: '',
          location,
          timeOfDay,
          mood,
          shotType,
          description,
          imageUrl,
          duration: 0,
        }),
      })
      const json = await res.json()
      if (!json.ok) throw new Error(json.error)
      toast.success('Frame committed to board')
      reloadScenes()
      // Light reset for the next frame — keep shotType & location for continuity.
      setTitle('')
      setDescription('')
      setImageUrl('')
      setSequence(String((scenes?.length ?? 0) + 1))
    } catch (e: any) {
      toast.error(e?.message || 'Commit failed')
    } finally {
      setSaving(false)
    }
  }

  async function deleteScene(id: string) {
    try {
      const res = await fetch(`/api/scenes?id=${id}`, { method: 'DELETE' })
      const json = await res.json()
      if (!json.ok) throw new Error(json.error)
      toast.success('Frame removed from board')
      reloadScenes()
    } catch (e: any) {
      toast.error(e?.message || 'Delete failed')
    }
  }

  const sortedScenes = React.useMemo(() => {
    return [...(scenes ?? [])].sort((a, b) => (a.sequence || 0) - (b.sequence || 0))
  }, [scenes])

  return (
    <div className="space-y-6">
      <ModuleHeader
        index="04"
        title="Cinematographer"
        subtitle="A shot-by-shot storyboard forge — compose, expose, and commit frames to the production board."
        icon={Clapperboard}
      />

      {!activeProject ? (
        <Panel className="p-0">
          <EmptyState
            icon={Clapperboard}
            title="Select a production"
            desc="Choose or greenlight a production in the header to begin boarding frames."
          />
        </Panel>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
          {/* LEFT — Composer + preview */}
          <div className="lg:col-span-3 space-y-4">
            <Panel className="p-0">
              <PanelHeader
                title="Frame Composer"
                desc="Compose the shot, expose the frame, commit to the board."
                right={<Tag tone="gold">{activeProject.title}</Tag>}
              />
              <div className="p-5 space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <Field label="Title">
                    <Input
                      value={title}
                      onChange={(e) => setTitle(e.target.value)}
                      placeholder="Crossing the Salt"
                      className="bg-background/60"
                    />
                  </Field>
                  <Field label="Sequence" hint="numeric">
                    <Input
                      type="number"
                      value={sequence}
                      onChange={(e) => setSequence(e.target.value)}
                      min={0}
                      className="bg-background/60"
                    />
                  </Field>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <Field label="Location">
                    <Input
                      value={location}
                      onChange={(e) => setLocation(e.target.value)}
                      placeholder="EXT. SALT FLATS — DUSK"
                      className="bg-background/60 font-mono text-sm"
                    />
                  </Field>
                  <Field label="Time of Day">
                    <Input
                      value={timeOfDay}
                      onChange={(e) => setTimeOfDay(e.target.value)}
                      placeholder="DUSK / MAGIC HOUR"
                      className="bg-background/60 font-mono text-sm"
                    />
                  </Field>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <Field label="Mood">
                    <Input
                      value={mood}
                      onChange={(e) => setMood(e.target.value)}
                      placeholder="desolate, sublime"
                      className="bg-background/60"
                    />
                  </Field>
                  <Field label="Shot Type">
                    <Select value={shotType} onValueChange={setShotType}>
                      <SelectTrigger className="bg-background/60">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {SHOT_TYPES.map((s) => (
                          <SelectItem key={s} value={s}>
                            {s}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </Field>
                </div>

                <Field label="Description" hint="3+ lines of action">
                  <Textarea
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    rows={3}
                    placeholder="A lone figure crosses the cracked earth toward the obelisk…"
                    className="resize-none bg-background/60 text-sm"
                    onKeyDown={(e) => {
                      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') exposeFrame()
                    }}
                  />
                </Field>

                <div className="flex flex-wrap items-center gap-2 pt-1">
                  <GenerateButton
                    variant="outline"
                    loading={img.loading}
                    onClick={exposeFrame}
                    icon={Aperture}
                  >
                    Expose Frame
                  </GenerateButton>
                  <PlatformSelector value={platform} onChange={setPlatform} />
                  <GenerateButton
                    loading={saving}
                    onClick={commitToBoard}
                    icon={Save}
                  >
                    Commit to Board
                  </GenerateButton>
                  <div className="flex-1" />
                  <span className="font-mono text-[10px] text-muted-foreground/60 uppercase tracking-wider hidden sm:inline">
                    ⌘ + ↵ to expose
                  </span>
                </div>
              </div>
            </Panel>

            {/* Preview frame */}
            <Panel className="p-0">
              <PanelHeader
                title="Exposed Frame"
                desc={shotType}
                right={
                  imageUrl ? (
                    <Tag tone="crimson">LIVE</Tag>
                  ) : (
                    <Tag tone="muted">{ASPECT_BY_SHOT[shotType] ?? '1344x768'}</Tag>
                  )
                }
              />
              <div className="p-4">
                {img.loading ? (
                  <ApertureLoader label="Exposing frame" />
                ) : (
                  <ImageFrame
                    src={imageUrl}
                    alt={title || 'Storyboard frame'}
                    aspect={aspectFor(shotType)}
                    shotType={shotType}
                    caption={title || undefined}
                  />
                )}
                {imageUrl && (
                  <p className="mt-3 text-[11px] text-muted-foreground/70 font-mono leading-relaxed break-words">
                    ▚ {buildPrompt().slice(0, 220)}…
                  </p>
                )}
              </div>
            </Panel>
          </div>

          {/* RIGHT — Storyboard board */}
          <div className="lg:col-span-2">
            <Panel className="p-0 h-full">
              <PanelHeader
                title="Storyboard Board"
                desc="Committed frames, in sequence."
                right={<Tag tone="muted">{sortedScenes.length}</Tag>}
              />
              <div className="p-3 max-h-[680px] overflow-y-auto scrollbar-muse space-y-3">
                {scenesLoading && (
                  <div className="p-4">
                    <Loader label="Loading board" />
                  </div>
                )}
                {!scenesLoading && sortedScenes.length === 0 && (
                  <EmptyState
                    icon={Clapperboard}
                    title="Board empty"
                    desc="Expose your first frame."
                  />
                )}
                {sortedScenes.map((s, idx) => (
                  <div
                    key={s.id}
                    className="rounded-md border border-border/70 bg-card/40 p-2 group"
                  >
                    <div className="flex items-center justify-between mb-2 px-1">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-[10px] text-gold/90 tracking-cinematic">
                          {frameLabel(idx)}
                        </span>
                        <span className="text-[10px] text-muted-foreground/60 font-mono">
                          SEQ {s.sequence}
                        </span>
                      </div>
                      <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7 text-muted-foreground hover:text-crimson"
                          onClick={() => deleteScene(s.id)}
                          title="Remove frame"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </div>
                    <ImageFrame
                      src={s.imageUrl}
                      alt={s.title}
                      aspect="aspect-video"
                      shotType={s.shotType}
                      caption={s.title}
                    />
                    <div className="flex items-center gap-2 mt-2 px-1 flex-wrap">
                      {s.location && (
                        <span className="font-mono text-[10px] text-muted-foreground/70 truncate">
                          {s.location}
                        </span>
                      )}
                      <span className="ml-auto flex items-center gap-1 text-[10px] text-muted-foreground/60">
                        <Clock className="h-3 w-3" />
                        {new Date(s.createdAt).toLocaleDateString('en-US', {
                          month: 'short',
                          day: 'numeric',
                        })}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </Panel>
          </div>
        </div>
      )}
    </div>
  )
}
