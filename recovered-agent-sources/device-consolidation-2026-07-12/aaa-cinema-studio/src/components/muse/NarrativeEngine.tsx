'use client'

import * as React from 'react'
import {
  ScrollText,
  Save,
  Trash2,
  Copy,
  FileText,
  Sparkles,
  Clock,
} from 'lucide-react'
import { useMuse } from '@/lib/store'
import {
  ModuleHeader,
  Panel,
  PanelHeader,
  Field,
  GenerateButton,
  Markdown,
  useGenerate,
  useFetch,
  EmptyState,
  Tag,
  copyToClipboard,
  Loader,
} from './shared'
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
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'

type Mode =
  | 'logline'
  | 'treatment'
  | 'beatsheet'
  | 'scene'
  | 'dialogue'
  | 'outline'
  | 'branches'
  | 'monologue'
  | 'pitch'
  | 'titlesequence'
  | 'gameplayloop'
  | 'leveldesign'
  | 'bossencounter'
  | 'cinebrief'
  | 'scorebrief'

type Tier = 'standard' | 'flagship'

interface FieldDef {
  key: string
  label: string
  type: 'input' | 'textarea' | 'number'
  placeholder?: string
  default?: string
  rows?: number
}

const MODES: { id: Mode; label: string; desc: string; fields: FieldDef[] }[] = [
  {
    id: 'logline',
    label: 'Logline',
    desc: 'The whole world in a single breath.',
    fields: [
      { key: 'title', label: 'Title', type: 'input', placeholder: 'The Last Cartographer' },
      { key: 'seed', label: 'Premise seed', type: 'textarea', placeholder: 'A mapmaker who can draw places that then become real…', rows: 2 },
    ],
  },
  {
    id: 'treatment',
    label: 'Treatment',
    desc: 'A 3-act or 8-sequence narrative beat sheet.',
    fields: [
      { key: 'title', label: 'Title', type: 'input' },
      { key: 'logline', label: 'Logline', type: 'textarea', rows: 2 },
      { key: 'structure', label: 'Structure', type: 'input', placeholder: 'three or eight (default three)', default: 'three' },
    ],
  },
  {
    id: 'beatsheet',
    label: 'Beat Sheet',
    desc: 'Blake-Snyder "Save the Cat" 15 beats.',
    fields: [
      { key: 'title', label: 'Title', type: 'input' },
      { key: 'logline', label: 'Logline', type: 'textarea', rows: 2 },
    ],
  },
  {
    id: 'scene',
    label: 'Scene',
    desc: 'Industry-format screenplay scene.',
    fields: [
      { key: 'location', label: 'Location', type: 'input', placeholder: 'INT. OBSERVATORY — NIGHT' },
      { key: 'timeOfDay', label: 'Time of day', type: 'input', placeholder: 'NIGHT' },
      { key: 'mood', label: 'Mood', type: 'input', placeholder: 'unsettling, hushed' },
      { key: 'characters', label: 'Characters present', type: 'input', placeholder: 'VEGA and the STRANGER' },
      { key: 'intent', label: 'Dramatic intent', type: 'input', placeholder: 'a secret is forced into the open' },
    ],
  },
  {
    id: 'dialogue',
    label: 'Dialogue',
    desc: 'Subtext-rich exchange.',
    fields: [
      { key: 'a', label: 'Character A', type: 'input', placeholder: 'VEGA' },
      { key: 'aDesc', label: 'A disposition', type: 'input', placeholder: 'guarded' },
      { key: 'b', label: 'Character B', type: 'input', placeholder: 'THE STRANGER' },
      { key: 'bDesc', label: 'B disposition', type: 'input', placeholder: 'pressing' },
      { key: 'tone', label: 'Tone', type: 'input', placeholder: 'tense' },
      { key: 'beats', label: 'Lines', type: 'number', default: '6' },
      { key: 'context', label: 'Context', type: 'textarea', rows: 2, placeholder: 'a reckoning long deferred' },
    ],
  },
  {
    id: 'outline',
    label: 'Outline',
    desc: 'Mission / episode structure.',
    fields: [
      { key: 'title', label: 'Title', type: 'input' },
      { key: 'episodes', label: 'Number of beats', type: 'number', default: '8' },
    ],
  },
  {
    id: 'branches',
    label: 'Branching Node',
    desc: 'Player-choice narrative node.',
    fields: [
      { key: 'situation', label: 'Situation', type: 'textarea', rows: 2, placeholder: 'a moral crossroads at the edge of the city' },
    ],
  },
  {
    id: 'monologue',
    label: 'Monologue',
    desc: 'Theatrical solo speech.',
    fields: [
      { key: 'who', label: 'Speaker', type: 'input', placeholder: 'the antagonist' },
      { key: 'archetype', label: 'Archetype', type: 'input', placeholder: 'the true believer' },
      { key: 'occasion', label: 'Occasion', type: 'input', placeholder: 'the moment before the irreversible act' },
      { key: 'voice', label: 'Voice', type: 'input', placeholder: 'lucid, lyrical, dangerous' },
      { key: 'words', label: 'Word count', type: 'number', default: '180' },
    ],
  },
  {
    id: 'pitch',
    label: 'Pitch',
    desc: 'Producer-ready pitch document.',
    fields: [
      { key: 'title', label: 'Title', type: 'input' },
    ],
  },
  {
    id: 'titlesequence',
    label: 'Title Sequence',
    desc: 'Shot-by-shot opening title design.',
    fields: [
      { key: 'title', label: 'Title', type: 'input' },
    ],
  },
  {
    id: 'gameplayloop',
    label: 'Gameplay Loop',
    desc: 'AAA core loop design brief.',
    fields: [
      { key: 'title', label: 'Title', type: 'input' },
    ],
  },
  {
    id: 'leveldesign',
    label: 'Level Design',
    desc: 'AAA level design brief.',
    fields: [
      { key: 'seed', label: 'Level concept', type: 'textarea', rows: 2, placeholder: 'the infiltration of the observatory' },
    ],
  },
  {
    id: 'bossencounter',
    label: 'Boss Encounter',
    desc: 'Phased AAA boss design.',
    fields: [
      { key: 'seed', label: 'Boss concept', type: 'textarea', rows: 2, placeholder: 'the cartographer who drew themselves out of existence' },
    ],
  },
  {
    id: 'cinebrief',
    label: 'Cinematography',
    desc: 'DP-ready cinematography brief.',
    fields: [
      { key: 'title', label: 'Title', type: 'input' },
      { key: 'seed', label: 'Sequence', type: 'textarea', rows: 2, placeholder: 'the confrontation at the map room' },
    ],
  },
  {
    id: 'scorebrief',
    label: 'Score & Sound',
    desc: 'Composer-ready score brief.',
    fields: [
      { key: 'title', label: 'Title', type: 'input' },
    ],
  },
]

function fmtDate(iso: string) {
  try {
    return new Date(iso).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
  } catch {
    return ''
  }
}

export function NarrativeEngine() {
  const { activeProject } = useMuse()
  const [mode, setMode] = React.useState<Mode>('scene')
  const [tier, setTier] = React.useState<Tier>('flagship')
  const [values, setValues] = React.useState<Record<string, string>>({})
  const [result, setResult] = React.useState<string>('')
  const [saving, setSaving] = React.useState(false)

  const { run, loading } = useGenerate<{ content: string }>('/api/narrative')
  const scriptsUrl = activeProject ? `/api/scripts?projectId=${activeProject.id}` : null
  const { data: scripts, reload: reloadScripts, loading: scriptsLoading } = useFetch<any[]>(scriptsUrl, [activeProject?.id])

  const modeDef = MODES.find((m) => m.id === mode)!

  React.useEffect(() => {
    // reset values when mode changes, applying defaults
    const next: Record<string, string> = {}
    modeDef.fields.forEach((f) => (next[f.key] = f.default ?? ''))
    setValues(next)
    setResult('')
  }, [mode])  

  async function generate() {
    const body: any = { mode, tier, ...values }
    if (activeProject) {
      body.genre = activeProject.genre
      body.medium = activeProject.medium
      if (!body.title && activeProject.title) body.title = activeProject.title
      if (!body.logline && activeProject.logline) body.logline = activeProject.logline
    }
    const data = await run(body, { errorMsg: 'Narrative engine stalled' })
    if (data?.content) setResult(data.content)
  }

  async function save() {
    if (!activeProject) return toast.error('Select a production first')
    if (!result.trim()) return toast.error('Nothing to save yet')
    setSaving(true)
    try {
      const res = await fetch('/api/scripts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          projectId: activeProject.id,
          title: `${modeDef.label} — ${new Date().toLocaleTimeString()}`,
          act: modeDef.label,
          kind: mode,
          content: result,
        }),
      })
      const json = await res.json()
      if (!json.ok) throw new Error(json.error)
      toast.success('Saved to script library')
      reloadScripts()
    } catch (e: any) {
      toast.error(e?.message || 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  async function deleteScript(id: string) {
    try {
      const res = await fetch(`/api/scripts?id=${id}`, { method: 'DELETE' })
      const json = await res.json()
      if (!json.ok) throw new Error(json.error)
      toast.success('Removed')
      reloadScripts()
    } catch (e: any) {
      toast.error(e?.message || 'Delete failed')
    }
  }

  return (
    <div className="space-y-6">
      <ModuleHeader
        index="02"
        title="Narrative Engine"
        subtitle="An LLM dramaturg for loglines, treatments, beat sheets, scenes, branching nodes, title sequences, gameplay loops, level & boss design, cinematography and score."
        icon={ScrollText}
      />

      {!activeProject && (
        <Panel className="p-0">
          <EmptyState icon={FileText} title="Select a production" desc="Choose or greenlight a production in the header to anchor your writing." />
        </Panel>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* Composer */}
        <div className="lg:col-span-3 space-y-4">
          <Panel className="p-0">
            <PanelHeader title="Composition" desc="Choose a form, set the scene, then call the muse." right={
              <div className="flex items-center gap-1">
                <button onClick={() => setTier('standard')} className={cn('rounded px-2 py-1 text-[10px] font-mono uppercase tracking-wider border transition-colors', tier === 'standard' ? 'border-border text-foreground bg-muted/40' : 'border-transparent text-muted-foreground/60 hover:text-foreground')}>Standard</button>
                <button onClick={() => setTier('flagship')} className={cn('rounded px-2 py-1 text-[10px] font-mono uppercase tracking-wider border transition-colors', tier === 'flagship' ? 'border-[#7ae0ff]/40 text-[#7ae0ff] bg-[#7ae0ff]/10' : 'border-transparent text-muted-foreground/60 hover:text-foreground')}>Flagship</button>
              </div>
            } />
            <div className="p-5 space-y-5">
              <div className="flex flex-wrap gap-2">
                {MODES.map((m) => (
                  <button
                    key={m.id}
                    onClick={() => setMode(m.id)}
                    className={cn(
                      'rounded-md px-3 py-1.5 text-xs font-medium border transition-colors',
                      mode === m.id
                        ? 'bg-[#7ae0ff]/10 border-[#7ae0ff]/40 text-[#7ae0ff]'
                        : 'border-border text-muted-foreground hover:text-foreground hover:border-border/80',
                    )}
                  >
                    {m.label}
                  </button>
                ))}
              </div>
              <p className="text-xs text-muted-foreground -mt-2">{modeDef.desc}</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {modeDef.fields.map((f) => (
                  <Field key={f.key} label={f.label} hint={f.type === 'number' ? 'numeric' : undefined}>
                    {f.type === 'textarea' ? (
                      <Textarea
                        value={values[f.key] ?? ''}
                        onChange={(e) => setValues((v) => ({ ...v, [f.key]: e.target.value }))}
                        placeholder={f.placeholder}
                        rows={f.rows ?? 3}
                        className="resize-none bg-background/60 text-sm"
                      />
                    ) : (
                      <Input
                        type={f.type === 'number' ? 'number' : 'text'}
                        value={values[f.key] ?? ''}
                        onChange={(e) => setValues((v) => ({ ...v, [f.key]: e.target.value }))}
                        placeholder={f.placeholder}
                        className="bg-background/60"
                      />
                    )}
                  </Field>
                ))}
              </div>
              <div className="flex items-center justify-between pt-1">
                <span className="font-mono text-[10px] text-muted-foreground/60 uppercase tracking-wider">⌘ + ↵ to generate</span>
                <GenerateButton loading={loading} onClick={generate} icon={Sparkles}>
                  Compose
                </GenerateButton>
              </div>
            </div>
          </Panel>

          {/* Result */}
          <Panel className="p-0">
            <PanelHeader
              title="Manuscript"
              desc="The generated artifact."
              right={
                result ? (
                  <div className="flex items-center gap-1">
                    <Button variant="ghost" size="sm" onClick={() => copyToClipboard(result)} className="text-muted-foreground hover:text-gold h-8">
                      <Copy className="h-3.5 w-3.5" />
                    </Button>
                    <Button variant="ghost" size="sm" onClick={save} disabled={saving} className="text-gold hover:text-gold gap-1.5 h-8">
                      <Save className="h-3.5 w-3.5" /> {saving ? 'Saving' : 'Save'}
                    </Button>
                  </div>
                ) : null
              }
            />
            <div className="p-5 min-h-[200px]">
              {loading ? (
                <div className="flex justify-center py-10"><Loader label="The muse is writing" /></div>
              ) : result ? (
                <Markdown content={result} />
              ) : (
                <EmptyState icon={ScrollText} title="Awaiting composition" desc="Set the scene and press Compose. The manuscript will appear here." />
              )}
            </div>
          </Panel>
        </div>

        {/* Library */}
        <div className="lg:col-span-2">
          <Panel className="p-0 h-full">
            <PanelHeader title="Script Library" desc="Saved drafts for this production." right={<Tag tone="muted">{scripts?.length ?? 0}</Tag>} />
            <div className="p-3 max-h-[640px] overflow-y-auto scrollbar-muse space-y-2">
              {scriptsLoading && <div className="p-4"><Loader label="Loading library" /></div>}
              {!scriptsLoading && (!scripts || scripts.length === 0) && (
                <EmptyState icon={FileText} title="Library empty" desc="Saved scripts will collect here." />
              )}
              {scripts?.map((s) => (
                <div key={s.id} className="rounded-md border border-border/70 bg-card/40 p-3 group">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <Tag tone="gold">{s.act}</Tag>
                        <span className="text-[11px] text-muted-foreground/70 font-mono">{s.kind}</span>
                      </div>
                      <p className="text-sm text-foreground mt-1 truncate font-medium">{s.title}</p>
                      <p className="text-[11px] text-muted-foreground/60 mt-0.5 flex items-center gap-1">
                        <Clock className="h-3 w-3" /> {fmtDate(s.createdAt)}
                      </p>
                    </div>
                    <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                      <Button variant="ghost" size="icon" className="h-7 w-7 text-muted-foreground hover:text-gold" onClick={() => copyToClipboard(s.content)}>
                        <Copy className="h-3.5 w-3.5" />
                      </Button>
                      <Button variant="ghost" size="icon" className="h-7 w-7 text-muted-foreground hover:text-crimson" onClick={() => deleteScript(s.id)}>
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </div>
                  <p className="text-xs text-muted-foreground/70 mt-2 line-clamp-2 whitespace-pre-wrap">{s.content.replace(/[#*]/g, '').slice(0, 120)}…</p>
                </div>
              ))}
            </div>
          </Panel>
        </div>
      </div>
    </div>
  )
}
