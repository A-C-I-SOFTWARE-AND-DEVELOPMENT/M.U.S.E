'use client'

import * as React from 'react'
import {
  Mic2,
  AudioLines,
  Clock,
  Copy,
  RotateCcw,
  UserRound,
  Clapperboard,
} from 'lucide-react'
import { useMuse } from '@/lib/store'
import {
  ModuleHeader,
  Panel,
  PanelHeader,
  Field,
  GenerateButton,
  Tag,
  EmptyState,
  Loader,
  useGenerate,
  useFetch,
  copyToClipboard,
} from './shared'
import { Textarea } from '@/components/ui/textarea'
import { Button } from '@/components/ui/button'
import { Slider } from '@/components/ui/slider'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import { VOICES, type MuseCharacter, type MuseVoiceTake } from '@/lib/types'

function fmtDate(iso: string) {
  try {
    return new Date(iso).toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    })
  } catch {
    return ''
  }
}

function voiceLabel(id: string): string {
  return VOICES.find((v) => v.id === id)?.label ?? id
}

export function VoiceStage() {
  const { activeProject } = useMuse()

  const charsUrl = activeProject ? `/api/characters?projectId=${activeProject.id}` : null
  const { data: cast, loading: castLoading } = useFetch<MuseCharacter[]>(charsUrl, [activeProject?.id])

  const projectUrl = activeProject ? `/api/projects/${activeProject.id}` : null
  const {
    data: project,
    loading: projectLoading,
    reload: reloadProject,
  } = useFetch<{ voiceTakes?: MuseVoiceTake[] }>(projectUrl, [activeProject?.id])

  const [text, setText] = React.useState('')
  const [voice, setVoice] = React.useState('default')
  const [speed, setSpeed] = React.useState(1)
  const [characterId, setCharacterId] = React.useState<string | null>(null)
  const [audioUrl, setAudioUrl] = React.useState<string>('')

  const { run, loading } = useGenerate<{ audioUrl: string; take: MuseVoiceTake }>('/api/voice')

  // Reset transient state when project changes
  React.useEffect(() => {
    setText('')
    setAudioUrl('')
    setCharacterId(null)
    setVoice('default')
    setSpeed(1)
  }, [activeProject?.id])

  function pickCharacter(c: MuseCharacter | null) {
    if (!c) {
      setCharacterId(null)
      setVoice('default')
      return
    }
    setCharacterId(c.id)
    if (c.voice) setVoice(c.voice)
  }

  async function perform() {
    if (!activeProject) return toast.error('Select a production first')
    if (!text.trim()) return toast.error('Write a line to perform')
    const data = await run(
      {
        text: text.trim(),
        voice,
        speed,
        projectId: activeProject.id,
        characterId: characterId ?? null,
        save: true,
      },
      { successMsg: 'Take recorded', errorMsg: 'Voice synthesis failed' },
    )
    if (data?.audioUrl) {
      setAudioUrl(data.audioUrl)
      setText('')
      reloadProject()
    }
  }

  const takes = project?.voiceTakes ?? []

  if (!activeProject) {
    return (
      <div className="space-y-6">
        <ModuleHeader
          index="06"
          title="Voice Stage"
          subtitle="A directed voice-acting booth. Six voices, any line, on demand."
          icon={Mic2}
        />
        <Panel className="p-0">
          <EmptyState
            icon={Mic2}
            title="Select a production"
            desc="Choose or greenlight a production in the header to open the booth."
          />
        </Panel>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <ModuleHeader
        index="06"
        title="Voice Stage"
        subtitle="A directed voice-acting booth. Six voices, any line, on demand."
        icon={Mic2}
      />

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* THE BOOTH */}
        <div className="lg:col-span-3 space-y-4">
          <Panel className="p-0">
            <PanelHeader
              title="The Booth"
              desc="Cast a voice. Read the line. Roll tape."
              right={
                <div className="flex items-center gap-2">
                  <span className="rec-dot inline-block h-1.5 w-1.5 rounded-full bg-crimson" />
                  <Tag tone="crimson">LIVE</Tag>
                </div>
              }
            />
            <div className="p-5 space-y-5">
              {/* Character picker */}
              <Field label="Cast the Voice" hint="optional">
                <div className="flex flex-wrap gap-2">
                  <button
                    onClick={() => pickCharacter(null)}
                    className={cn(
                      'rounded-md px-3 py-1.5 text-xs font-medium border transition-colors',
                      characterId === null
                        ? 'bg-gold/10 border-gold/40 text-gold'
                        : 'border-border text-muted-foreground hover:text-foreground hover:border-border/80',
                    )}
                  >
                    Original / No character
                  </button>
                  {castLoading && (
                    <span className="inline-flex items-center gap-1.5 px-2 py-1.5 text-[11px] text-muted-foreground/70">
                      <Loader label="Loading cast" />
                    </span>
                  )}
                  {cast?.map((c) => (
                    <button
                      key={c.id}
                      onClick={() => pickCharacter(c)}
                      className={cn(
                        'rounded-md px-3 py-1.5 text-xs font-medium border transition-colors flex items-center gap-1.5',
                        characterId === c.id
                          ? 'bg-gold/10 border-gold/40 text-gold'
                          : 'border-border text-muted-foreground hover:text-foreground hover:border-border/80',
                      )}
                    >
                      {c.portraitUrl ? (
                         
                        <img
                          src={c.portraitUrl}
                          alt={c.name}
                          className="h-4 w-4 rounded-full object-cover"
                        />
                      ) : (
                        <UserRound className="h-3 w-3" />
                      )}
                      {c.name}
                    </button>
                  ))}
                </div>
              </Field>

              {/* Line */}
              <Field label="Line" hint="mono">
                <Textarea
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  rows={4}
                  placeholder="You were never going to make it to the coast, were you?"
                  className="resize-none bg-background/60 font-mono text-sm"
                  onKeyDown={(e) => {
                    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') perform()
                  }}
                />
              </Field>

              {/* Voice + Speed */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <Field label="Voice">
                  <Select value={voice} onValueChange={setVoice}>
                    <SelectTrigger className="bg-background/60">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {VOICES.map((v) => (
                        <SelectItem key={v.id} value={v.id}>
                          {v.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </Field>
                <Field label="Speed" hint={`${speed.toFixed(1)}×`}>
                  <div className="pt-2.5">
                    <Slider
                      value={[speed]}
                      min={0.5}
                      max={1.5}
                      step={0.1}
                      onValueChange={(v) => setSpeed(v[0] ?? 1)}
                      className="cursor-pointer"
                    />
                    <div className="flex justify-between mt-1.5 text-[10px] font-mono text-muted-foreground/60 uppercase tracking-wider">
                      <span>0.5×</span>
                      <span>1.0×</span>
                      <span>1.5×</span>
                    </div>
                  </div>
                </Field>
              </div>

              <div className="flex items-center justify-between pt-1">
                <span className="font-mono text-[10px] text-muted-foreground/60 uppercase tracking-wider">
                  ⌘ + ↵ to perform
                </span>
                <GenerateButton loading={loading} onClick={perform} icon={Mic2}>
                  Perform
                </GenerateButton>
              </div>
            </div>
          </Panel>

          {/* AUDIO PLAYER */}
          {audioUrl && (
            <Panel className="p-0">
              <PanelHeader
                title="Latest Take"
                desc="Review the read. Re-perform to try again."
                right={
                  <div className="flex items-center gap-2">
                    <span className="rec-dot inline-block h-1.5 w-1.5 rounded-full bg-crimson" />
                    <Tag tone="crimson">TAKE</Tag>
                  </div>
                }
              />
              <div className="p-5 space-y-4">
                <div className="rounded-md border border-border/70 bg-black/40 p-3">
                  <audio controls src={audioUrl} className="w-full" />
                </div>
                <div className="flex items-center justify-end">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setAudioUrl('')}
                    className="text-muted-foreground hover:text-crimson gap-1.5"
                  >
                    <RotateCcw className="h-3.5 w-3.5" />
                    Re-perform
                  </Button>
                </div>
              </div>
            </Panel>
          )}
        </div>

        {/* TAKE LOG */}
        <div className="lg:col-span-2">
          <Panel className="p-0 h-full">
            <PanelHeader
              title="Take Log"
              desc="Recorded takes for this production."
              right={<Tag tone="muted">{takes.length}</Tag>}
            />
            <div className="p-3 max-h-[680px] overflow-y-auto scrollbar-muse space-y-2">
              {projectLoading && (
                <div className="p-4">
                  <Loader label="Loading takes" />
                </div>
              )}
              {!projectLoading && takes.length === 0 && (
                <EmptyState
                  icon={AudioLines}
                  title="No takes yet"
                  desc="Perform your first line — it will appear here."
                />
              )}
              {takes.map((t) => {
                const who = cast?.find((c) => c.id === t.characterId)
                return (
                  <div
                    key={t.id}
                    className="rounded-md border border-border/70 bg-card/40 p-3 group"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2 min-w-0">
                        <Tag tone="gold">{voiceLabel(t.voice)}</Tag>
                        {who && <Tag tone="muted">{who.name}</Tag>}
                      </div>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6 text-muted-foreground hover:text-gold opacity-0 group-hover:opacity-100"
                        onClick={() => copyToClipboard(t.text, 'Line copied')}
                      >
                        <Copy className="h-3 w-3" />
                      </Button>
                    </div>
                    <p className="text-sm text-foreground/90 mt-2 line-clamp-2 whitespace-pre-wrap font-mono leading-snug">
                      {t.text}
                    </p>
                    <audio
                      controls
                      src={t.audioBase64}
                      className="h-8 w-full mt-2"
                    />
                    <p className="text-[10px] text-muted-foreground/60 mt-1.5 flex items-center gap-1 font-mono">
                      <Clock className="h-3 w-3" />
                      {fmtDate(t.createdAt)}
                    </p>
                  </div>
                )
              })}
            </div>
          </Panel>
        </div>
      </div>

      {/* Footer ledger */}
      <div className="flex items-center gap-2 text-[11px] font-mono text-muted-foreground/60 uppercase tracking-wider px-1">
        <Clapperboard className="h-3.5 w-3.5" />
        <span>{takes.length} take{s(takes.length)} on file for {activeProject.title}</span>
      </div>
    </div>
  )
}

function s(n: number) {
  return n === 1 ? '' : 's'
}
