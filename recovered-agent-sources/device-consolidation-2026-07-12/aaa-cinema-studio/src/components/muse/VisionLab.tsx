'use client'

import * as React from 'react'
import {
  ScanEye,
  Upload,
  Link2,
  Copy,
  Film,
  Image as ImageIcon,
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
  ImageFrame,
  Markdown,
  useGenerate,
  copyToClipboard,
} from './shared'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'

type Mode = 'describe' | 'style' | 'character' | 'storyboard' | 'moodboard'

const MODES: { id: Mode; label: string; desc: string }[] = [
  { id: 'describe', label: 'Describe', desc: 'Full production design brief.' },
  { id: 'style', label: 'Style DNA', desc: 'Reusable generative prompt template.' },
  { id: 'character', label: 'Character', desc: 'Reverse-engineer the subject.' },
  { id: 'storyboard', label: 'Storyboard', desc: 'Read it as a single boarded frame.' },
  { id: 'moodboard', label: 'Moodboard', desc: 'Mood statement + palette + next tile.' },
]

export function VisionLab() {
  const { activeProject } = useMuse()

  const [imageUrl, setImageUrl] = React.useState('')
  const [urlInput, setUrlInput] = React.useState('')
  const [mode, setMode] = React.useState<Mode>('describe')
  const [uploading, setUploading] = React.useState(false)
  const [result, setResult] = React.useState('')

  const { run, loading } = useGenerate<{ content: string; mode: Mode }>('/api/vision')

  function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    if (!file.type.startsWith('image/')) {
      toast.error('Please choose an image file')
      return
    }
    setUploading(true)
    const reader = new FileReader()
    reader.onload = () => {
      const src = String(reader.result ?? '')
      setImageUrl(src)
      setUrlInput('')
      setUploading(false)
    }
    reader.onerror = () => {
      toast.error('Could not read file')
      setUploading(false)
    }
    reader.readAsDataURL(file)
  }

  function applyUrl() {
    const v = urlInput.trim()
    if (!v) return
    if (!/^https?:\/\//i.test(v)) {
      toast.error('Paste a full http(s) image URL')
      return
    }
    setImageUrl(v)
  }

  async function analyze() {
    if (!imageUrl) return toast.error('Add a reference frame first')
    const data = await run(
      { imageUrl, mode },
      { errorMsg: 'Vision analysis failed' },
    )
    if (data?.content) setResult(data.content)
  }

  return (
    <div className="space-y-6">
      <ModuleHeader
        index="07"
        title="Vision Lab"
        subtitle="A VLM reference analyst. Upload any frame — receive a production brief, style DNA, character read, or storyboard breakdown."
        icon={ScanEye}
      />

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* COMPOSER + OUTPUT */}
        <div className="lg:col-span-3 space-y-4">
          {/* Reference frame */}
          <Panel className="p-0">
            <PanelHeader
              title="Reference Frame"
              desc="Upload an image or paste a URL — the VLM will read it."
              right={
                activeProject ? <Tag tone="gold">{activeProject.title}</Tag> : <Tag tone="muted">No production</Tag>
              }
            />
            <div className="p-5 space-y-4">
              <ImageFrame
                src={imageUrl}
                alt="Reference frame"
                loading={uploading}
                aspect="aspect-video"
                shotType="REFERENCE"
                caption={imageUrl ? (imageUrl.startsWith('data:') ? 'Uploaded reference' : imageUrl) : undefined}
              />

              <div className="flex flex-col sm:flex-row gap-3">
                <label className="cursor-pointer flex-1">
                  <input
                    type="file"
                    accept="image/*"
                    onChange={onFile}
                    className="sr-only"
                  />
                  <span className="inline-flex items-center justify-center gap-2 rounded-md border border-gold/40 bg-gold/10 text-gold px-4 py-2 text-sm font-medium hover:bg-gold/20 transition-colors w-full">
                    <Upload className="h-4 w-4" />
                    Upload Reference
                  </span>
                </label>
              </div>

              <Field label="or paste URL" hint="http(s)">
                <div className="flex gap-2">
                  <Input
                    value={urlInput}
                    onChange={(e) => setUrlInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') applyUrl()
                    }}
                    placeholder="https://example.com/frame.jpg"
                    className="bg-background/60"
                  />
                  <Button
                    variant="outline"
                    onClick={applyUrl}
                    disabled={!urlInput.trim()}
                    className="border-gold/40 text-gold hover:bg-gold/10 hover:text-gold gap-1.5"
                  >
                    <Link2 className="h-3.5 w-3.5" />
                    Load
                  </Button>
                </div>
              </Field>
            </div>
          </Panel>

          {/* Output */}
          <Panel className="p-0">
            <PanelHeader
              title="Analysis"
              desc="The VLM read of the frame."
              right={
                result ? (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => copyToClipboard(result)}
                    className="text-muted-foreground hover:text-gold h-8"
                  >
                    <Copy className="h-3.5 w-3.5" />
                  </Button>
                ) : null
              }
            />
            <div className="p-5 min-h-[240px]">
              {loading ? (
                <div className="flex justify-center py-10">
                  <Loader label="Reading the frame" />
                </div>
              ) : result ? (
                <Markdown content={result} />
              ) : (
                <EmptyState
                  icon={ScanEye}
                  title="No analysis yet"
                  desc="Add a reference frame and choose a mode to read it."
                />
              )}
            </div>
          </Panel>
        </div>

        {/* MODE PICKER + META */}
        <div className="lg:col-span-2 space-y-4">
          <Panel className="p-0">
            <PanelHeader title="Reading Mode" desc="What should the VLM extract?" />
            <div className="p-3 space-y-2">
              {MODES.map((m) => (
                <button
                  key={m.id}
                  onClick={() => setMode(m.id)}
                  className={cn(
                    'w-full text-left rounded-md border p-3 transition-colors group',
                    mode === m.id
                      ? 'bg-gold/10 border-gold/40'
                      : 'border-border/70 hover:border-border bg-card/30',
                  )}
                >
                  <div className="flex items-center justify-between">
                    <span
                      className={cn(
                        'font-display text-sm font-semibold',
                        mode === m.id ? 'text-gold' : 'text-foreground',
                      )}
                    >
                      {m.label}
                    </span>
                    {mode === m.id && (
                      <span className="rec-dot inline-block h-1.5 w-1.5 rounded-full bg-crimson" />
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground mt-0.5">{m.desc}</p>
                </button>
              ))}
            </div>
            <div className="px-3 pb-4">
              <GenerateButton
                loading={loading}
                onClick={analyze}
                icon={ScanEye}
                className="w-full"
                disabled={!imageUrl}
              >
                Analyze Frame
              </GenerateButton>
              {!imageUrl && (
                <p className="text-[10px] text-muted-foreground/60 mt-2 text-center font-mono uppercase tracking-wider">
                  Add a reference first
                </p>
              )}
            </div>
          </Panel>

          <Panel className="p-0">
            <PanelHeader title="Frame State" desc="Current reference." />
            <div className="p-4 space-y-2 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground/70 uppercase tracking-wider font-mono text-[10px]">Source</span>
                <Tag tone={imageUrl ? 'gold' : 'muted'}>
                  {imageUrl ? (imageUrl.startsWith('data:') ? 'Upload' : 'URL') : 'None'}
                </Tag>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground/70 uppercase tracking-wider font-mono text-[10px]">Mode</span>
                <Tag tone="crimson">{MODES.find((m) => m.id === mode)?.label}</Tag>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground/70 uppercase tracking-wider font-mono text-[10px]">Project</span>
                <Tag tone="muted">{activeProject ? activeProject.title : 'Standalone'}</Tag>
              </div>
            </div>
          </Panel>

          <div className="flex items-center gap-2 text-[11px] font-mono text-muted-foreground/60 uppercase tracking-wider px-1">
            <ImageIcon className="h-3.5 w-3.5" />
            <span>VLM reads any frame into a brief.</span>
          </div>
        </div>
      </div>

      {/* Bottom film strip */}
      <div className="flex items-center gap-2 text-[11px] font-mono text-muted-foreground/60 uppercase tracking-wider px-1">
        <Film className="h-3.5 w-3.5" />
        <span>Vision Lab — standalone tool{activeProject ? ` · linked to ${activeProject.title}` : ''}.</span>
      </div>
    </div>
  )
}
