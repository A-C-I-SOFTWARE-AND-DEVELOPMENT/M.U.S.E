'use client'

import * as React from 'react'
import {
  Drama,
  Sparkles,
  Save,
  Trash2,
  Wand2,
  Aperture,
  UserPlus,
  Mic2,
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
  Markdown,
  useGenerate,
  useFetch,
  EmptyState,
  Tag,
  Loader,
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
import { VOICES, type MuseCharacter } from '@/lib/types'

const ROLES = ['Protagonist', 'Antagonist', 'Supporting', 'Faction Lead', 'Cameo']

function extractSection(md: string, heading: string): string {
  const re = new RegExp(`###\\s*${heading}\\s*\\n([\\s\\S]*?)(?=\\n###|$)`, 'i')
  const m = md.match(re)
  return m ? m[1].trim().replace(/\s+/g, ' ') : ''
}

export function CharacterForge() {
  const { activeProject } = useMuse()
  const [name, setName] = React.useState('')
  const [role, setRole] = React.useState('Protagonist')
  const [archetype, setArchetype] = React.useState('')
  const [appearance, setAppearance] = React.useState('')
  const [voiceProfile, setVoiceProfile] = React.useState('')
  const [voice, setVoice] = React.useState('default')
  const [backstory, setBackstory] = React.useState('')
  const [dossier, setDossier] = React.useState('')
  const [portrait, setPortrait] = React.useState('')
  const [platform, setPlatform] = React.useState<string | undefined>(undefined)
  const [saving, setSaving] = React.useState(false)

  const bio = useGenerate<{ content: string }>('/api/narrative')
  const img = useGenerate<{ imageUrl: string }>('/api/generate-image')
  const charsUrl = activeProject ? `/api/characters?projectId=${activeProject.id}` : null
  const { data: cast, reload: reloadCast, loading: castLoading } = useFetch<MuseCharacter[]>(charsUrl, [activeProject?.id])

  React.useEffect(() => {
    setName(''); setArchetype(''); setAppearance(''); setVoiceProfile('')
    setBackstory(''); setDossier(''); setPortrait('')
  }, [activeProject?.id])

  async function developDossier() {
    if (!activeProject) return toast.error('Select a production first')
    if (!name.trim()) return toast.error('Name the character first')
    const data = await bio.run(
      {
        mode: 'bio',
        name,
        role,
        archetype: archetype || 'the haunted professional',
        genre: activeProject.genre,
        medium: activeProject.medium,
        projectTitle: activeProject.title,
      },
      { successMsg: 'Dossier developed', errorMsg: 'The dramaturg stalled' },
    )
    if (data?.content) {
      setDossier(data.content)
      const app = extractSection(data.content, 'APPEARANCE')
      const voi = extractSection(data.content, 'VOICE')
      const back = extractSection(data.content, 'BACKSTORY')
      if (app) setAppearance(app)
      if (voi) setVoiceProfile(voi)
      if (back) setBackstory(back)
    }
  }

  function buildPortraitPrompt(): string {
    const parts = [
      'cinematic character portrait',
      name && `of ${name}`,
      `a ${role.toLowerCase()}`,
      archetype && `archetype: ${archetype}`,
      appearance,
      voiceProfile && `(vocal quality hints: ${voiceProfile})`,
      activeProject?.genre && `${activeProject.genre} aesthetic`,
      activeProject?.palette && `palette: ${activeProject.palette}`,
      'dramatic Rembrandt lighting, shallow depth of field, 85mm, ultra detailed, film grain, theatrical, painterly, AAA concept art',
    ].filter(Boolean)
    return parts.join(', ')
  }

  async function forgePortrait() {
    if (!activeProject) return toast.error('Select a production first')
    if (!name.trim()) return toast.error('Name the character first')
    const prompt = buildPortraitPrompt()
    const data = await img.run(
      { prompt, size: '768x1344', type: 'portrait', title: name, projectId: activeProject.id, platform },
      { successMsg: 'Portrait exposed', errorMsg: 'Imager stalled' },
    )
    if (data?.imageUrl) setPortrait(data.imageUrl)
  }

  async function saveToCast() {
    if (!activeProject) return toast.error('Select a production first')
    if (!name.trim()) return toast.error('Name the character first')
    setSaving(true)
    try {
      const res = await fetch('/api/characters', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          projectId: activeProject.id,
          name,
          role,
          archetype,
          appearance,
          voiceProfile,
          voice,
          backstory: dossier || backstory,
          portraitUrl: portrait,
        }),
      })
      const json = await res.json()
      if (!json.ok) throw new Error(json.error)
      toast.success(`${name} joined the cast`)
      reloadCast()
      // reset for next
      setName(''); setArchetype(''); setAppearance(''); setVoiceProfile('')
      setBackstory(''); setDossier(''); setPortrait('')
    } catch (e: any) {
      toast.error(e?.message || 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  async function removeCharacter(id: string) {
    try {
      const res = await fetch(`/api/characters?id=${id}`, { method: 'DELETE' })
      const json = await res.json()
      if (!json.ok) throw new Error(json.error)
      toast.success('Removed from cast')
      reloadCast()
    } catch (e: any) {
      toast.error(e?.message || 'Delete failed')
    }
  }

  return (
    <div className="space-y-6">
      <ModuleHeader
        index="03"
        title="Character Forge"
        subtitle="Develop a casting-ready dossier, forge a portrait, and lock the voice — then commit to the cast."
        icon={Drama}
      />

      {!activeProject ? (
        <Panel className="p-0"><EmptyState icon={Drama} title="Select a production" desc="Choose or greenlight a production to forge its cast." /></Panel>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
          {/* Form + dossier */}
          <div className="lg:col-span-3 space-y-4">
            <Panel className="p-0">
              <PanelHeader title="Character Sheet" desc="Identity, appearance & voice." right={<Tag tone="gold">{activeProject.title}</Tag>} />
              <div className="p-5 space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <Field label="Name">
                    <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Vega Aldous" className="bg-background/60" />
                  </Field>
                  <Field label="Role">
                    <Select value={role} onValueChange={setRole}>
                      <SelectTrigger className="bg-background/60"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {ROLES.map((r) => <SelectItem key={r} value={r}>{r}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </Field>
                </div>
                <Field label="Archetype" hint="e.g. the reluctant hero">
                  <Input value={archetype} onChange={(e) => setArchetype(e.target.value)} placeholder="the true believer" className="bg-background/60" />
                </Field>
                <Field label="Appearance" hint="auto-filled from dossier">
                  <Textarea value={appearance} onChange={(e) => setAppearance(e.target.value)} rows={2} placeholder="Face, build, signature garment, distinguishing mark…" className="resize-none bg-background/60 text-sm" />
                </Field>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <Field label="Voice Profile" hint="for casting">
                    <Input value={voiceProfile} onChange={(e) => setVoiceProfile(e.target.value)} placeholder="smoky alto, faint Glasgow" className="bg-background/60" />
                  </Field>
                  <Field label="Voice Actor">
                    <Select value={voice} onValueChange={setVoice}>
                      <SelectTrigger className="bg-background/60"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {VOICES.map((v) => <SelectItem key={v.id} value={v.id}>{v.label}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </Field>
                </div>
                <Field label="Backstory">
                  <Textarea value={backstory} onChange={(e) => setBackstory(e.target.value)} rows={3} placeholder="Origin, the wound, want vs. need…" className="resize-none bg-background/60 text-sm" />
                </Field>

                <div className="flex flex-wrap items-center gap-2 pt-1">
                  <GenerateButton variant="outline" loading={bio.loading} onClick={developDossier} icon={Wand2}>
                    Develop Dossier
                  </GenerateButton>
                  <GenerateButton variant="outline" loading={img.loading} onClick={forgePortrait} icon={Aperture}>
                    Forge Portrait
                  </GenerateButton>
                  <PlatformSelector value={platform} onChange={setPlatform} />
                  <div className="flex-1" />
                  <GenerateButton loading={saving} onClick={saveToCast} icon={Save}>
                    Commit to Cast
                  </GenerateButton>
                </div>
              </div>
            </Panel>

            {dossier && (
              <Panel className="p-0">
                <PanelHeader title="Character Dossier" desc="Generated dramaturgy." right={<Tag tone="crimson">LLM</Tag>} />
                <div className="p-5">
                  {bio.loading ? <Loader label="Developing dossier" /> : <Markdown content={dossier} />}
                </div>
              </Panel>
            )}
          </div>

          {/* Portrait + cast */}
          <div className="lg:col-span-2 space-y-4">
            <Panel className="p-0">
              <PanelHeader title="Portrait" desc="Generative key art." />
              <div className="p-4">
                <ImageFrame src={portrait} alt={name || 'Character portrait'} loading={img.loading} aspect="aspect-[3/4]" shotType="PORTRAIT" caption={name || undefined} />
                {portrait && (
                  <p className="mt-3 text-[11px] text-muted-foreground/70 font-mono leading-relaxed break-words">
                    ▚ {buildPortraitPrompt().slice(0, 180)}…
                  </p>
                )}
              </div>
            </Panel>

            <Panel className="p-0">
              <PanelHeader title="The Cast" desc={`${cast?.length ?? 0} committed`} right={<Tag tone="muted">{activeProject.title}</Tag>} />
              <div className="p-3 max-h-[420px] overflow-y-auto scrollbar-muse space-y-2">
                {castLoading && <div className="p-3"><Loader label="Loading cast" /></div>}
                {!castLoading && (!cast || cast.length === 0) && (
                  <EmptyState icon={UserPlus} title="Cast is empty" desc="Develop and commit characters to build your ensemble." />
                )}
                {cast?.map((c) => (
                  <div key={c.id} className="flex gap-3 rounded-md border border-border/70 bg-card/40 p-2.5 group">
                    <div className="h-16 w-12 shrink-0 overflow-hidden rounded border border-border bg-black">
                      {c.portraitUrl ? (
                         
                        <img src={c.portraitUrl} alt={c.name} className="h-full w-full object-cover" />
                      ) : (
                        <div className="h-full w-full flex items-center justify-center"><Drama className="h-4 w-4 text-muted-foreground/40" /></div>
                      )}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-semibold text-foreground truncate">{c.name}</span>
                        <Tag tone="gold">{c.role}</Tag>
                      </div>
                      {c.archetype && <p className="text-[11px] text-muted-foreground/70 italic truncate">{c.archetype}</p>}
                      <div className="flex items-center gap-1 mt-1 text-[10px] text-muted-foreground/60">
                        <Mic2 className="h-3 w-3" />
                        <span className="truncate">{VOICES.find((v) => v.id === c.voice)?.label ?? c.voice}</span>
                      </div>
                    </div>
                    <Button variant="ghost" size="icon" className="h-7 w-7 text-muted-foreground hover:text-crimson opacity-0 group-hover:opacity-100" onClick={() => removeCharacter(c.id)}>
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
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
