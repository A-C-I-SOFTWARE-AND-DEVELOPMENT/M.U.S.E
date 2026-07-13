'use client'

import * as React from 'react'
import {
  Radio,
  Plug,
  Send,
  Trash2,
  KeyRound,
  RefreshCw,
  ExternalLink,
  Loader2,
  CheckCircle2,
  XCircle,
} from 'lucide-react'
import {
  ModuleHeader,
  Panel,
  PanelHeader,
  Field,
  EmptyState,
  Tag,
} from './shared'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import {
  getGatewayBase,
  setGatewayBase,
  getToken,
  setToken,
  clearToken,
  pingHealth,
  pairStart,
  pairConfirm,
  chat,
  DEFAULT_GATEWAY_BASE,
  TOKEN_EVENT,
  type ChatTurn,
} from '@/lib/muse-gateway'

type ConnState = 'unknown' | 'checking' | 'online' | 'offline'
type Msg = { role: 'user' | 'asst'; text: string }

export function GatewayBridge() {
  const [base, setBase] = React.useState(getGatewayBase())
  const [token, setTok] = React.useState(getToken())
  const [conn, setConn] = React.useState<ConnState>('unknown')

  // Pairing flow state
  const [deviceName, setDeviceName] = React.useState('')
  const [pairCode, setPairCode] = React.useState('')
  const [phrase, setPhrase] = React.useState('')
  const [pairing, setPairing] = React.useState(false)
  const [pairMsg, setPairMsg] = React.useState('')

  // Chat state
  const [messages, setMessages] = React.useState<Msg[]>([])
  const [draft, setDraft] = React.useState('')
  const [sending, setSending] = React.useState(false)
  const logRef = React.useRef<HTMLDivElement | null>(null)

  // Listen for token changes (e.g. from paste/pair)
  React.useEffect(() => {
    const refresh = () => setTok(getToken())
    window.addEventListener(TOKEN_EVENT, refresh)
    window.addEventListener('storage', refresh)
    return () => {
      window.removeEventListener(TOKEN_EVENT, refresh)
      window.removeEventListener('storage', refresh)
    }
  }, [])

  // Auto-scroll chat
  React.useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [messages])

  // Health check
  const checkHealth = React.useCallback(async () => {
    setConn('checking')
    const r = await pingHealth(base)
    setConn(r.reachable ? 'online' : 'offline')
    return r
  }, [base])

  React.useEffect(() => {
    checkHealth()
    const t = setInterval(checkHealth, 15000)
    return () => clearInterval(t)
  }, [checkHealth])

  function saveBase() {
    setGatewayBase(base)
    toast.success('Gateway saved')
    checkHealth()
  }

  async function startPair() {
    setPairing(true)
    setPairMsg('Requesting pairing code…')
    const r = await pairStart(base, deviceName)
    setPairing(false)
    if (!r.ok) {
      setPairMsg('Pairing unavailable: ' + (r.error || '') + (r.hint ? ' — ' + r.hint : ''))
      return
    }
    setPairCode(r.pairingCode || '')
    setPairMsg('Code generated. Enter the owner authorization phrase, then confirm.')
  }

  async function confirmPair() {
    if (!pairCode) {
      setPairMsg('Get a pairing code first.')
      return
    }
    setPairing(true)
    setPairMsg('Confirming…')
    const r = await pairConfirm(base, pairCode, phrase)
    setPairing(false)
    if (r.forbidden) {
      setPairMsg('Owner authorization required — re-enter the exact phrase.')
      return
    }
    if (!r.ok || !r.token) {
      setPairMsg('Pairing failed: ' + (r.error || ''))
      return
    }
    setPhrase('')
    setPairCode('')
    setPairMsg('Paired. This device now has its own token.')
    setTok(r.token)
    toast.success('Paired with muse gateway')
  }

  function pasteToken() {
    const t = window.prompt('Paste a muse gateway token:')
    if (t && t.trim()) {
      setToken(t.trim())
      setTok(t.trim())
      toast.success('Token saved')
    }
  }

  function disconnect() {
    clearToken()
    setTok('')
    setMessages([])
    toast.success('Disconnected')
  }

  async function send() {
    const p = draft.trim()
    if (!p || sending) return
    if (!token) {
      toast.error('Pair this device first')
      return
    }
    setDraft('')
    setSending(true)
    const history: ChatTurn[] = messages.map((m) => ({
      role: m.role === 'user' ? 'user' : 'assistant',
      content: m.text,
    }))
    setMessages((prev) => [...prev, { role: 'user', text: p }, { role: 'asst', text: '…' }])
    await chat(p, history, {
      onDelta: (acc) =>
        setMessages((prev) => {
          const next = prev.slice()
          next[next.length - 1] = { role: 'asst', text: acc || '…' }
          return next
        }),
      onError: (m) =>
        setMessages((prev) => {
          const next = prev.slice()
          next[next.length - 1] = { role: 'asst', text: m }
          return next
        }),
    })
    setSending(false)
  }

  const paired = !!token
  const connLabel =
    conn === 'online' ? 'online' : conn === 'offline' ? 'offline' : conn === 'checking' ? 'connecting…' : 'unknown'

  return (
    <div className="space-y-6">
      <ModuleHeader
        index="12"
        title="Gateway Bridge"
        subtitle="Connect to the muse gateway — the synaptic substrate. Pair this device, then talk to the mind in real time. Defaults to musehq.io."
        icon={Radio}
      />

      {/* Connection panel */}
      <Panel className="p-0">
        <PanelHeader
          title="Connection"
          desc="The gateway base URL and this device's auth token."
          right={
            <div className="flex items-center gap-2">
              <span className={cn('h-2 w-2 rounded-full', conn === 'online' ? 'core-dot rec-dot' : conn === 'offline' ? 'bg-[#ff5c63]' : 'bg-muted-foreground/50')} />
              <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">{connLabel}</span>
              <Button variant="ghost" size="sm" onClick={checkHealth} className="h-7 text-muted-foreground hover:text-foreground gap-1">
                <RefreshCw className={cn('h-3 w-3', conn === 'checking' && 'animate-spin')} /> Retry
              </Button>
            </div>
          }
        />
        <div className="p-5 space-y-4">
          <Field label="Gateway base URL" hint="defaults to musehq.io">
            <div className="flex gap-2">
              <Input
                value={base}
                onChange={(e) => setBase(e.target.value)}
                placeholder={DEFAULT_GATEWAY_BASE}
                className="bg-background/60"
              />
              <Button variant="outline" onClick={saveBase} className="bg-transparent border-border text-foreground hover:bg-muted/40 gap-1.5 shrink-0">
                Save
              </Button>
            </div>
          </Field>

          <div className="flex flex-wrap items-center gap-2">
            {paired ? (
              <>
                <Tag tone="spectral">PAIRED</Tag>
                <span className="font-mono text-[11px] text-muted-foreground truncate max-w-[260px]">
                  token: {token.slice(0, 10)}…{token.slice(-4)}
                </span>
                <div className="flex-1" />
                <Button variant="ghost" size="sm" onClick={pasteToken} className="text-muted-foreground hover:text-foreground gap-1.5 h-8">
                  <KeyRound className="h-3.5 w-3.5" /> Replace token
                </Button>
                <Button variant="ghost" size="sm" onClick={disconnect} className="text-[#ff5c63] hover:text-[#ff5c63] gap-1.5 h-8">
                  <Trash2 className="h-3.5 w-3.5" /> Disconnect
                </Button>
              </>
            ) : (
              <>
                <Tag tone="muted">UNPAIRED</Tag>
                <div className="flex-1" />
                <Button variant="ghost" size="sm" onClick={pasteToken} className="text-muted-foreground hover:text-foreground gap-1.5 h-8">
                  <KeyRound className="h-3.5 w-3.5" /> Paste token
                </Button>
              </>
            )}
          </div>

          <div className="flex items-center gap-2 text-[11px] font-mono text-muted-foreground/70 uppercase tracking-wider">
            <ExternalLink className="h-3 w-3" />
            <a href={base || DEFAULT_GATEWAY_BASE} target="_blank" rel="noreferrer" className="hover:text-[#7ae0ff] transition-colors truncate">
              {base || DEFAULT_GATEWAY_BASE}
            </a>
          </div>
        </div>
      </Panel>

      {/* Pairing flow — only when unpaired */}
      {!paired && (
        <Panel className="p-0">
          <PanelHeader title="Owner-Gated Pairing" desc="Generate a short-lived code, then confirm with the owner authorization phrase." right={<Tag tone="violet">OWNER-GATED</Tag>} />
          <div className="p-5 space-y-4">
            <Field label="Device name (optional)">
              <Input value={deviceName} onChange={(e) => setDeviceName(e.target.value)} placeholder="muse web client" className="bg-background/60" />
            </Field>
            <div className="flex flex-wrap items-center gap-2">
              <Button onClick={startPair} disabled={pairing} className="bg-white text-[#04060c] hover:bg-white/90 gap-2">
                {pairing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plug className="h-4 w-4" />}
                Get pairing code
              </Button>
              {pairCode && <span className="font-mono text-xs text-[#7ae0ff]">code: {pairCode}</span>}
            </div>
            {pairCode && (
              <div className="space-y-2">
                <Field label="Owner authorization phrase">
                  <Input
                    type="password"
                    value={phrase}
                    onChange={(e) => setPhrase(e.target.value)}
                    placeholder="Yes, with authorization."
                    className="bg-background/60"
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') confirmPair()
                    }}
                  />
                </Field>
                <Button onClick={confirmPair} disabled={pairing} variant="outline" className="bg-transparent border-[#7ae0ff]/40 text-[#7ae0ff] hover:bg-[#7ae0ff]/10 gap-2">
                  {pairing ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
                  Confirm &amp; pair
                </Button>
              </div>
            )}
            {pairMsg && <p className="text-xs text-muted-foreground">{pairMsg}</p>}
          </div>
        </Panel>
      )}

      {/* Live chat — only when paired */}
      <Panel className="p-0">
        <PanelHeader
          title="Talk to muse"
          desc="Streamed live from the gateway mind."
          right={
            paired ? (
              <Tag tone="spectral">
                <span className="core-dot rec-dot h-1.5 w-1.5 rounded-full inline-block mr-1" /> live
              </Tag>
            ) : (
              <Tag tone="muted">offline</Tag>
            )
          }
        />
        <div className="p-0">
          {paired ? (
            <>
              <div ref={logRef} className="max-h-[44vh] min-h-[220px] overflow-y-auto scrollbar-muse p-4 flex flex-col gap-2.5">
                {messages.length === 0 ? (
                  <div className="flex items-center justify-center h-full text-sm text-muted-foreground/60 py-10">
                    Ask muse anything. Responses stream live from the gateway.
                  </div>
                ) : (
                  messages.map((m, i) => (
                    <div
                      key={i}
                      className={cn(
                        'rounded-lg px-3 py-2 text-sm whitespace-pre-wrap break-words max-w-[88%] border',
                        m.role === 'user'
                          ? 'self-end bg-muted/40 border-border text-foreground'
                          : 'self-start bg-[#0a0f1c] border-border spectral-edge-left text-foreground/95',
                      )}
                    >
                      {m.text}
                    </div>
                  ))
                )}
              </div>
              <div className="flex gap-2 p-3 border-t border-border">
                <Input
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  placeholder="Message muse…  (Enter to send)"
                  className="bg-background/60"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault()
                      send()
                    }
                  }}
                />
                <Button onClick={send} disabled={sending || !draft.trim()} className="bg-white text-[#04060c] hover:bg-white/90 gap-2 shrink-0">
                  {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                  Send
                </Button>
              </div>
            </>
          ) : (
            <EmptyState
              icon={XCircle}
              title="Not paired"
              desc="Pair this device (or paste a token) above to talk to the muse mind."
            />
          )}
        </div>
      </Panel>

      <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-[11px] font-mono text-muted-foreground/70 uppercase tracking-wider px-1">
        <span>Gateway Bridge</span>
        <span className="text-border">·</span>
        <span>contract: /v1/health · /v1/cockpit/pair · /v1/jarvis/chat (NDJSON)</span>
        <span className="text-border">·</span>
        <span className="text-[#7ae0ff]">mirrors apps/desktop/ui/src/lib/gateway.ts</span>
      </div>
    </div>
  )
}
