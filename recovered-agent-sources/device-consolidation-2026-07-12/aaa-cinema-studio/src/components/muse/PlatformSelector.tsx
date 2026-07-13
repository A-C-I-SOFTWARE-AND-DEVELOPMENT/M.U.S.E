'use client'

import * as React from 'react'
import { Gamepad2, Monitor } from 'lucide-react'
import {
  PLATFORMS,
  ERAS,
  getPlatform,
  type Platform,
  type Era,
} from '@/lib/platforms'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import { cn } from '@/lib/utils'

/**
 * PlatformSelector — a compact trigger that opens a grid of console platforms
 * grouped by era. Used by every image-generating module to target a specific
 * console generation (PS1, PS2, PS3, PS4, PS5, Xbox family, Nintendo family).
 */
export function PlatformSelector({
  value,
  onChange,
  className,
  allowNone = true,
}: {
  value?: string
  onChange: (id: string | undefined) => void
  className?: string
  allowNone?: boolean
}) {
  const [open, setOpen] = React.useState(false)
  const current = getPlatform(value)

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          className={cn(
            'inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-xs font-medium transition-colors',
            current
              ? 'border-[#7ae0ff]/40 bg-[#7ae0ff]/10 text-[#7ae0ff]'
              : 'border-border bg-muted/30 text-muted-foreground hover:text-foreground hover:border-border',
            className,
          )}
        >
          {current ? (
            <>
              <span
                className="h-2 w-2 rounded-sm"
                style={{ background: current.accent }}
              />
              <span className="font-mono uppercase tracking-wider">{current.code}</span>
              <span className="hidden sm:inline text-foreground/80">{current.label}</span>
            </>
          ) : (
            <>
              <Monitor className="h-3.5 w-3.5" />
              <span>Modern (default)</span>
            </>
          )}
        </button>
      </PopoverTrigger>
      <PopoverContent
        className="w-[340px] p-0 glass-strong border-border"
        align="start"
        sideOffset={6}
      >
        <div className="px-3 py-2 border-b border-border flex items-center gap-2">
          <Gamepad2 className="h-4 w-4 text-[#7ae0ff]" />
          <span className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
            Platform Fidelity
          </span>
        </div>
        <div className="max-h-[360px] overflow-y-auto scrollbar-muse">
          {allowNone && (
            <button
              onClick={() => {
                onChange(undefined)
                setOpen(false)
              }}
              className={cn(
                'w-full flex items-center gap-2 px-3 py-2 text-left text-xs hover:bg-muted/40 transition-colors border-b border-border/50',
                !value && 'bg-[#7ae0ff]/10 text-[#7ae0ff]',
              )}
            >
              <Monitor className="h-3.5 w-3.5" />
              <span className="font-medium">Modern / Photoreal</span>
              <span className="ml-auto text-[10px] text-muted-foreground font-mono">default</span>
            </button>
          )}
          {ERAS.map((era) => {
            const platforms = PLATFORMS.filter((p) => p.era === era.id)
            return (
              <div key={era.id} className="border-b border-border/50 last:border-0">
                <div className="px-3 py-1.5 flex items-center justify-between bg-muted/20">
                  <span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
                    {era.label}
                  </span>
                  <span className="text-[10px] font-mono text-muted-foreground/60">{era.range}</span>
                </div>
                <div className="grid grid-cols-1">
                  {platforms.map((p) => (
                    <PlatformRow
                      key={p.id}
                      p={p}
                      active={value === p.id}
                      onClick={() => {
                        onChange(p.id)
                        setOpen(false)
                      }}
                    />
                  ))}
                </div>
              </div>
            )
          })}
        </div>
      </PopoverContent>
    </Popover>
  )
}

function PlatformRow({
  p,
  active,
  onClick,
}: {
  p: Platform
  active: boolean
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'w-full flex items-center gap-2.5 px-3 py-2 text-left text-xs hover:bg-muted/40 transition-colors',
        active && 'bg-[#7ae0ff]/10',
      )}
    >
      <span
        className="h-3 w-3 rounded-sm shrink-0 border border-white/10"
        style={{ background: p.accent }}
      />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className={cn('font-medium', active ? 'text-[#7ae0ff]' : 'text-foreground')}>
            {p.label}
          </span>
          <span className="font-mono text-[10px] text-muted-foreground/70">{p.code}</span>
        </div>
        <div className="text-[10px] text-muted-foreground/60 truncate">{p.maker} · {p.year}</div>
      </div>
      {active && <span className="rec-dot h-1.5 w-1.5 rounded-full core-dot" />}
    </button>
  )
}

/** Compact era badge row — used in the Fidelity Lab. */
export function EraTabs({
  value,
  onChange,
}: {
  value: Era
  onChange: (e: Era) => void
}) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {ERAS.map((e) => (
        <button
          key={e.id}
          onClick={() => onChange(e.id)}
          className={cn(
            'rounded-md px-3 py-1.5 text-xs font-medium border transition-colors',
            value === e.id
              ? 'bg-[#7ae0ff]/10 border-[#7ae0ff]/40 text-[#7ae0ff]'
              : 'border-border text-muted-foreground hover:text-foreground hover:border-border/80',
          )}
        >
          {e.label}
          <span className="ml-1.5 text-[10px] text-muted-foreground/60 font-mono">{e.range}</span>
        </button>
      ))}
    </div>
  )
}
