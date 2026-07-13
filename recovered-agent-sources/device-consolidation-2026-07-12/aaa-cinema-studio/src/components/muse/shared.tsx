'use client'

import * as React from 'react'
import { Loader2, Sparkles, Film, Clapperboard } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import ReactMarkdown from 'react-markdown'

// ---------- Loader ----------
export function Loader({ label = 'Rendering' }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-muted-foreground text-xs uppercase tracking-cinematic">
      <Loader2 className="h-3.5 w-3.5 animate-spin text-gold" />
      <span>{label}</span>
    </div>
  )
}

export function ApertureLoader({ label = 'Composing frame' }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-12 text-muted-foreground">
      <div className="relative h-12 w-12">
        <div className="absolute inset-0 rounded-full border border-border" />
        <div className="absolute inset-0 rounded-full border-t border-gold animate-spin" />
        <Film className="absolute inset-0 m-auto h-5 w-5 text-gold/70" />
      </div>
      <span className="text-xs uppercase tracking-cinematic">{label}…</span>
    </div>
  )
}

// ---------- ModuleHeader ----------
export function ModuleHeader({
  index,
  title,
  subtitle,
  icon: Icon,
  accent = 'spectral',
}: {
  index: string
  title: string
  subtitle: string
  icon: React.ComponentType<{ className?: string }>
  accent?: 'spectral' | 'danger'
}) {
  return (
    <div className="flex items-start gap-4 mb-6">
      <div
        className={cn(
          'flex h-12 w-12 shrink-0 items-center justify-center rounded-lg border',
          accent === 'spectral'
            ? 'border-[#7ae0ff]/30 bg-[#7ae0ff]/10 text-[#7ae0ff]'
            : 'border-[#ff5c63]/30 bg-[#ff5c63]/10 text-[#ff5c63]',
        )}
      >
        <Icon className="h-6 w-6" />
      </div>
      <div className="min-w-0">
        <div className="flex items-center gap-3">
          <span className="font-mono text-[10px] text-muted-foreground tracking-cinematic">
            {index}
          </span>
          <span className="h-px w-8 bg-border" />
          <span className="rec-dot inline-block h-1.5 w-1.5 rounded-full core-dot" />
          <span className="font-mono text-[10px] text-[#7ae0ff] tracking-cinematic">LIVE</span>
        </div>
        <h1 className="font-display text-2xl md:text-3xl font-semibold text-foreground mt-1">
          {title}
        </h1>
        <p className="text-sm text-muted-foreground mt-0.5 max-w-2xl">{subtitle}</p>
      </div>
    </div>
  )
}

// ---------- Panel / Card ----------
export function Panel({
  className,
  children,
  spotlight,
}: {
  className?: string
  children: React.ReactNode
  spotlight?: boolean
}) {
  return (
    <div
      className={cn(
        'tonal-card rounded-xl relative overflow-hidden',
        spotlight && 'spectral-edge-left',
        className,
      )}
    >
      {children}
    </div>
  )
}

export function PanelHeader({
  title,
  desc,
  right,
}: {
  title: string
  desc?: string
  right?: React.ReactNode
}) {
  return (
    <div className="flex items-start justify-between gap-3 px-5 pt-4 pb-3 border-b border-border/60">
      <div>
        <h3 className="font-display text-base font-semibold text-foreground">{title}</h3>
        {desc && <p className="text-xs text-muted-foreground mt-0.5">{desc}</p>}
      </div>
      {right}
    </div>
  )
}

// ---------- EmptyState ----------
export function EmptyState({
  icon: Icon,
  title,
  desc,
  action,
}: {
  icon: React.ComponentType<{ className?: string }>
  title: string
  desc?: string
  action?: React.ReactNode
}) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-12 px-6">
      <div className="flex h-14 w-14 items-center justify-center rounded-full border border-border bg-card/50 mb-4">
        <Icon className="h-6 w-6 text-muted-foreground" />
      </div>
      <p className="font-display text-lg text-foreground">{title}</p>
      {desc && <p className="text-sm text-muted-foreground mt-1 max-w-sm">{desc}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

// ---------- Tag / Pill ----------
export function Tag({
  children,
  tone = 'spectral',
}: {
  children: React.ReactNode
  tone?: 'spectral' | 'violet' | 'danger' | 'muted' | 'core'
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-sm px-2 py-0.5 text-[10px] font-mono uppercase tracking-wider border',
        tone === 'spectral' && 'border-[#7ae0ff]/30 bg-[#7ae0ff]/10 text-[#7ae0ff]',
        tone === 'violet' && 'border-[#b388ff]/30 bg-[#b388ff]/10 text-[#b388ff]',
        tone === 'danger' && 'border-[#ff5c63]/30 bg-[#ff5c63]/10 text-[#ff5c63]',
        tone === 'core' && 'border-white/40 bg-white/10 text-white',
        tone === 'muted' && 'border-border bg-muted/40 text-muted-foreground',
      )}
    >
      {children}
    </span>
  )
}

// ---------- ImageFrame ----------
export function ImageFrame({
  src,
  alt,
  loading,
  aspect = 'aspect-video',
  className,
  caption,
  shotType,
}: {
  src?: string
  alt: string
  loading?: boolean
  aspect?: string
  className?: string
  caption?: string
  shotType?: string
}) {
  return (
    <div className={cn('relative overflow-hidden rounded-md border border-border bg-black', aspect, className)}>
      <div className="film-edge absolute top-0 inset-x-0 h-2 opacity-50" />
      <div className="film-edge absolute bottom-0 inset-x-0 h-2 opacity-50" />
      {loading ? (
        <div className="absolute inset-0 flex items-center justify-center bg-black/60 shimmer">
          <div className="flex flex-col items-center justify-center gap-2 text-[#7ae0ff]">
            <Clapperboard className="h-6 w-6" />
            <span className="text-[10px] uppercase tracking-cinematic">Exposing frame</span>
          </div>
        </div>
      ) : src ? (
        <img src={src} alt={alt} className="h-full w-full object-cover" />
      ) : (
        <div className="absolute inset-0 flex items-center justify-center text-muted-foreground/40">
          <Film className="h-8 w-8" />
        </div>
      )}
      {shotType && !loading && (
        <span className="absolute top-3 left-3 z-10">
          <Tag tone="spectral">{shotType}</Tag>
        </span>
      )}
      {caption && !loading && (
        <div className="absolute bottom-2 inset-x-2 truncate rounded bg-black/60 px-2 py-1 text-[11px] text-foreground/90 font-mono">
          {caption}
        </div>
      )}
    </div>
  )
}

// ---------- Markdown ----------
export function Markdown({ content, className }: { content: string; className?: string }) {
  return (
    <div
      className={cn(
        'muse-prose text-sm leading-relaxed text-foreground/90',
        '[&_h1]:font-display [&_h1]:text-xl [&_h1]:font-semibold [&_h1]:text-gold [&_h1]:mt-4 [&_h1]:mb-2',
        '[&_h2]:font-display [&_h2]:text-lg [&_h2]:font-semibold [&_h2]:text-foreground [&_h2]:mt-4 [&_h2]:mb-2',
        '[&_h3]:font-display [&_h3]:text-xs [&_h3]:font-semibold [&_h3]:text-gold/90 [&_h3]:mt-3 [&_h3]:mb-1.5 [&_h3]:uppercase [&_h3]:tracking-wider',
        '[&_p]:my-2 [&_li]:my-1 [&_strong]:text-foreground [&_em]:text-crimson',
        '[&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5',
        '[&_blockquote]:border-l-2 [&_blockquote]:border-gold/50 [&_blockquote]:pl-3 [&_blockquote]:italic [&_blockquote]:text-muted-foreground',
        '[&_code]:rounded [&_code]:bg-muted/50 [&_code]:px-1 [&_code]:py-0.5 [&_code]:font-mono [&_code]:text-xs [&_code]:text-gold',
        '[&_pre]:bg-black/40 [&_pre]:rounded-md [&_pre]:p-3 [&_pre]:overflow-x-auto [&_pre]:border [&_pre]:border-border',
        '[&_a]:text-gold [&_a]:underline',
        '[&_hr]:my-4 [&_hr]:border-border',
        '[&_table]:w-full [&_th]:text-left [&_th]:text-xs [&_th]:uppercase [&_th]:tracking-wider [&_th]:text-muted-foreground [&_th]:py-1 [&_td]:py-1 [&_td]:border-t [&_td]:border-border',
        className,
      )}
    >
      <ReactMarkdown>{content}</ReactMarkdown>
    </div>
  )
}

// ---------- Generate button ----------
export function GenerateButton({
  loading,
  onClick,
  children = 'Generate',
  disabled,
  icon: Icon = Sparkles,
  variant = 'default',
  className,
}: {
  loading?: boolean
  onClick: () => void
  children?: React.ReactNode
  disabled?: boolean
  icon?: React.ComponentType<{ className?: string }>
  variant?: 'default' | 'outline' | 'secondary' | 'ghost'
  className?: string
}) {
  return (
    <Button
      onClick={onClick}
      disabled={loading || disabled}
      variant={variant}
      className={cn(
        'gap-2 bg-white text-[#04060c] hover:bg-white/90 font-semibold',
        variant !== 'default' && 'bg-transparent border-[#7ae0ff]/40 text-[#7ae0ff] hover:bg-[#7ae0ff]/10 hover:border-[#7ae0ff]',
        className,
      )}
    >
      {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Icon className="h-4 w-4" />}
      {children}
    </Button>
  )
}

// ---------- Field ----------
export function Field({
  label,
  hint,
  children,
}: {
  label: string
  hint?: string
  children: React.ReactNode
}) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <Label className="text-xs uppercase tracking-wider text-muted-foreground">{label}</Label>
        {hint && <span className="text-[10px] text-muted-foreground/70">{hint}</span>}
      </div>
      {children}
    </div>
  )
}

// ---------- useGenerate hook ----------
export function useGenerate<T = any>(url: string) {
  const [loading, setLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [data, setData] = React.useState<T | null>(null)

  const run = React.useCallback(
    async (body: any, opts?: { successMsg?: string; errorMsg?: string }) => {
      setLoading(true)
      setError(null)
      try {
        const res = await fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        })
        const json = await res.json()
        if (!json.ok) throw new Error(json.error || 'Request failed')
        setData(json.data)
        if (opts?.successMsg) toast.success(opts.successMsg)
        return json.data
      } catch (e: any) {
        const msg = e?.message || opts?.errorMsg || 'Generation failed'
        setError(msg)
        toast.error(msg)
        return null
      } finally {
        setLoading(false)
      }
    },
    [url],
  )

  return { loading, error, data, run, setData }
}

// ---------- useFetch hook (GET) ----------
export function useFetch<T = any>(url: string | null, deps: any[] = []) {
  const [data, setData] = React.useState<T | null>(null)
  const [loading, setLoading] = React.useState(!!url)
  const [error, setError] = React.useState<string | null>(null)

  const reload = React.useCallback(async () => {
    if (!url) return
    setLoading(true)
    try {
      const res = await fetch(url)
      const json = await res.json()
      if (!json.ok) throw new Error(json.error || 'Fetch failed')
      setData(json.data)
      setError(null)
    } catch (e: any) {
      setError(e?.message || 'Fetch failed')
    } finally {
      setLoading(false)
    }
     
  }, [url])

  React.useEffect(() => {
    reload()
     
  }, [url, ...deps])

  return { data, loading, error, reload, setData }
}

// ---------- Copy helper ----------
export async function copyToClipboard(text: string, msg = 'Copied to clipboard') {
  try {
    await navigator.clipboard.writeText(text)
    toast.success(msg)
  } catch {
    toast.error('Copy failed')
  }
}

// ---------- PromptComposer ----------
export function PromptComposer({
  value,
  onChange,
  placeholder,
  rows = 3,
  onGenerate,
  loading,
  generateLabel = 'Generate',
  extras,
}: {
  value: string
  onChange: (v: string) => void
  placeholder?: string
  rows?: number
  onGenerate: () => void
  loading?: boolean
  generateLabel?: string
  extras?: React.ReactNode
}) {
  return (
    <div className="space-y-3">
      <Textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        rows={rows}
        className="resize-none bg-background/60 font-mono text-sm"
        onKeyDown={(e) => {
          if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') onGenerate()
        }}
      />
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">{extras}</div>
        <GenerateButton loading={loading} onClick={onGenerate}>
          {generateLabel}
        </GenerateButton>
      </div>
    </div>
  )
}

// ---------- TitleInput ----------
export function TitleInput({
  value,
  onChange,
  placeholder = 'Title',
}: {
  value: string
  onChange: (v: string) => void
  placeholder?: string
}) {
  return (
    <Input
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      className="bg-background/60"
    />
  )
}
