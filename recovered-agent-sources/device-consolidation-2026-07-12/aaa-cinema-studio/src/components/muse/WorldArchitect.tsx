'use client'

import * as React from 'react'
import {
  Globe2,
  Save,
  Trash2,
  Copy,
  BookOpen,
  Clock,
  Palette,
  Lock,
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
import { toast } from 'sonner'
import { cn } from '@/lib/utils'

type Mode = 'world' | 'location' | 'faction' | 'lore' | 'palette'

interface FieldDef {
  key: string
  label: string
  type: 'input' | 'textarea'
  placeholder?: string
  default?: string
  rows?: number
}

const MODES: { id: Mode; label: string; desc: string; fields: FieldDef[] }[] = [
  {
    id: 'world',
    label: 'World',
    desc: 'Cosmology, geography, factions, conflict engine — the whole stage.',
    fields: [
      { key: 'title', label: 'Title', type: 'input', placeholder: 'The Salt Empire' },
      { key: 'seed', label: 'Seed', type: 'textarea', placeholder: 'a fading empire built on borrowed time', rows: 2 },
    ],
  },
  {
    id: 'location',
    label: 'Location',
    desc: 'A signature place — sensory, architectural, secret-bearing.',
    fields: [
      { key: 'seed', label: 'Seed', type: 'textarea', placeholder: 'a place that remembers', rows: 2 },
    ],
  },
  {
    id: 'faction',
    label: 'Faction',
    desc: 'Name, creed, hierarchy, resources, rivals.',
    fields: [
      { key: 'seed', label: 'Seed', type: 'textarea', placeholder: 'those who inherit the dead god\'s debt', rows: 2 },
    ],
  },
  {
    id: 'lore',
    label: 'Lore',
    desc: 'In-world artifact — scripture, field report, folk song.',
    fields: [
      { key: 'seed', label: 'Subject', type: 'textarea', placeholder: 'the thing beneath the ice', rows: 2 },
    ],
  },
  {
    id: 'palette',
    label: 'Palette',
    desc: 'Color, materials, light — lockable to the production.',
    fields: [
      { key: 'title', label: 'Title', type: 'input', placeholder: '(defaults to production title)' },
    ],
  },
]

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

export function WorldArchitect() {
  const { activeProject, upsertProject } = useMuse()
  const [mode, setMode] = React.useState<Mode>('world')
  const [values, setValues] = React.useState<Record<string, string>>({})
  const [result, setResult] = React.useState('')
  const [saving, setSaving] = React.useState(false)
  const [locking, setLocking] = React.useState(false)

  const { run, loading } = useGenerate<{ content: string; mode: Mode }>('/api/world')
  const scriptsUrl = activeProject ? `/api/scripts?projectId=${activeProject.id}` : null
  const { data: scripts, reload: reloadScripts, loading: scriptsLoading } = useFetch<any[]>(
    scriptsUrl,
    [activeProject?.id],
  )

  const modeDef = MODES.find((m) => m.id === mode)!
  const codex = React.useMemo(
    () => (scripts ?? []).filter((s) => s.kind === 'world'),
    [scripts],
  )

  React.useEffect(() => {
    const next: Record<string, string> = {}
    modeDef.fields.forEach((f) => (next[f.key] = f.default ?? ''))
    setValues(next)
    setResult('')
  }, [mode])  

  async function architect() {
    if (!activeProject) return toast.error('Select a production first')
    const body: any = {
      mode,
      ...values,
      genre: activeProject.genre,
      medium: activeProject.medium,
      title: values.title || activeProject.title,
    }
    const data = await run(body, { errorMsg: 'World architect stalled' })
    if (data?.content) setResult(data.content)
  }

  async function saveToCodex() {
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
          kind: 'world',
          content: result,
        }),
      })
      const json = await res.json()
      if (!json.ok) throw new Error(json.error)
      toast.success('Saved to codex')
      reloadScripts()
    } catch (e: any) {
      toast.error(e?.message || 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  async function lockPalette() {
    if (!activeProject) return toast.error('Select a production first')
    if (!result.trim()) return toast.error('Generate a palette first')
    setLocking(true)
    try {
      // Trim to a concise summary — keep the first 500 chars (covers KEY COLORS + MATERIALS).
      const summary = result.replace(/[#*]/g, '').slice(0, 500).trim()
      const res = await fetch(`/api/projects/${activeProject.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ palette: summary }),
      })
      const json = await res.json()
      if (!json.ok) throw new Error(json.error)
      // Reflect the locked palette in the local store so MissionControl etc. update.
      upsertProject({ ...activeProject, palette: summary, updatedAt: new Date().toISOString() })
      toast.success('Palette locked')
    } catch (e: any) {
      toast.error(e?.message || 'Lock failed')
    } finally {
      setLocking(false)
    }
  }

  async function deleteEntry(id: string) {
    try {
      const res = await fetch(`/api/scripts?id=${id}`, { method: 'DELETE' })
      const json = await res.json()
      if (!json.ok) throw new Error(json.error)
      toast.success('Removed from codex')
      reloadScripts()
    } catch (e: any) {
      toast.error(e?.message || 'Delete failed')
    }
  }

  return (
    <div className="space-y-6">
      <ModuleHeader
        index="05"
        title="World Architect"
        subtitle="A worldbuilding console — cosmologies, locations, factions, lore and palettes you can lock to the production."
        icon={Globe2}
      />

      {!activeProject ? (
        <Panel className="p-0">
          <EmptyState
            icon={Globe2}
            title="Select a production"
            desc="Choose or greenlight a production in the header before architecting its world."
          />
        </Panel>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
          {/* LEFT — Composer + output */}
          <div className="lg:col-span-3 space-y-4">
            <Panel className="p-0">
              <PanelHeader
                title="Composition"
                desc="Choose a mode, plant a seed, then call the architect."
                right={<Tag tone="gold">{activeProject.title}</Tag>}
              />
              <div className="p-5 space-y-5">
                <div className="flex flex-wrap gap-2">
                  {MODES.map((m) => (
                    <button
                      key={m.id}
                      onClick={() => setMode(m.id)}
                      className={cn(
                        'rounded-md px-3 py-1.5 text-xs font-medium border transition-colors',
                        mode === m.id
                          ? 'bg-gold/10 border-gold/40 text-gold'
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
                    <Field
                      key={f.key}
                      label={f.label}
                      hint={f.key === 'title' && mode === 'palette' ? 'optional' : undefined}
                    >
                      {f.type === 'textarea' ? (
                        <Textarea
                          value={values[f.key] ?? ''}
                          onChange={(e) => setValues((v) => ({ ...v, [f.key]: e.target.value }))}
                          placeholder={f.placeholder}
                          rows={f.rows ?? 3}
                          className="resize-none bg-background/60 text-sm"
                          onKeyDown={(e) => {
                            if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') architect()
                          }}
                        />
                      ) : (
                        <Input
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
                  <span className="font-mono text-[10px] text-muted-foreground/60 uppercase tracking-wider">
                    ⌘ + ↵ to architect
                  </span>
                  <GenerateButton loading={loading} onClick={architect} icon={Globe2}>
                    Architect
                  </GenerateButton>
                </div>
              </div>
            </Panel>

            {/* Output */}
            <Panel className="p-0">
              <PanelHeader
                title="World Codex Entry"
                desc="The generated artifact."
                right={
                  result ? (
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => copyToClipboard(result)}
                        className="text-muted-foreground hover:text-gold h-8"
                        title="Copy"
                      >
                        <Copy className="h-3.5 w-3.5" />
                      </Button>
                      {mode === 'palette' && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={lockPalette}
                          disabled={locking}
                          className="text-crimson hover:text-crimson gap-1.5 h-8"
                          title="Lock palette to production"
                        >
                          <Lock className="h-3.5 w-3.5" /> {locking ? 'Locking' : 'Lock Palette'}
                        </Button>
                      )}
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={saveToCodex}
                        disabled={saving}
                        className="text-gold hover:text-gold gap-1.5 h-8"
                      >
                        <Save className="h-3.5 w-3.5" /> {saving ? 'Saving' : 'Save to Codex'}
                      </Button>
                    </div>
                  ) : null
                }
              />
              <div className="p-5 min-h-[220px]">
                {loading ? (
                  <div className="flex justify-center py-10">
                    <Loader label="Architecting the world" />
                  </div>
                ) : result ? (
                  <Markdown content={result} />
                ) : (
                  <EmptyState
                    icon={mode === 'palette' ? Palette : Globe2}
                    title="Awaiting the architect"
                    desc="Plant a seed and press Architect. The codex entry will appear here."
                  />
                )}
              </div>
            </Panel>
          </div>

          {/* RIGHT — Codex library */}
          <div className="lg:col-span-2">
            <Panel className="p-0 h-full">
              <PanelHeader
                title="Codex Library"
                desc="Saved worldbuilding entries."
                right={<Tag tone="muted">{codex.length}</Tag>}
              />
              <div className="p-3 max-h-[700px] overflow-y-auto scrollbar-muse space-y-2">
                {scriptsLoading && (
                  <div className="p-4">
                    <Loader label="Loading codex" />
                  </div>
                )}
                {!scriptsLoading && codex.length === 0 && (
                  <EmptyState
                    icon={BookOpen}
                    title="Codex empty"
                    desc="Saved world entries will collect here."
                  />
                )}
                {codex.map((s) => (
                  <div
                    key={s.id}
                    className="rounded-md border border-border/70 bg-card/40 p-3 group"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <Tag tone="gold">{s.act}</Tag>
                          <span className="text-[11px] text-muted-foreground/70 font-mono">world</span>
                        </div>
                        <p className="text-sm text-foreground mt-1 truncate font-medium">{s.title}</p>
                        <p className="text-[11px] text-muted-foreground/60 mt-0.5 flex items-center gap-1">
                          <Clock className="h-3 w-3" /> {fmtDate(s.createdAt)}
                        </p>
                      </div>
                      <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7 text-muted-foreground hover:text-gold"
                          onClick={() => copyToClipboard(s.content)}
                        >
                          <Copy className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7 text-muted-foreground hover:text-crimson"
                          onClick={() => deleteEntry(s.id)}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </div>
                    <p className="text-xs text-muted-foreground/70 mt-2 line-clamp-2 whitespace-pre-wrap">
                      {s.content.replace(/[#*]/g, '').slice(0, 120)}…
                    </p>
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
