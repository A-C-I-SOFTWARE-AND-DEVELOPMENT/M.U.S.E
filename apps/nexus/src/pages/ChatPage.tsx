import { useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import {
  getChatConfig,
  setChatConfig,
  streamChat,
  gatewayHealth,
  effectiveTransport,
  modelsFor,
  type ChatMessage,
} from '@/lib/chat';
import { hasDirectKey } from '@/lib/directProvider';
import { resolveModelTransport } from '@/lib/providers';

export default function ChatPage() {
  const [cfg, setCfg] = useState(getChatConfig());
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [providers, setProviders] = useState<Record<string, boolean> | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const transport = effectiveTransport(cfg);
  // 'server' routes to the app's own /api/chat — we can always attempt it; the
  // edge function answers an honest 501 ('server chat not configured') if the
  // server holds no key, which surfaces as an error/disconnected state on send.
  const ready = transport === 'server' ? true : transport === 'direct' ? hasDirectKey() : !!providers;
  // Honest, granular label for the selected model's actual route. The old code
  // hardcoded "direct · OpenRouter", which mislabels Anthropic/Gemini/Groq/etc.
  // direct routes now that the multi-provider transport layer exists.
  const rt = resolveModelTransport(cfg.model);
  const transportLabel =
    cfg.mode === 'gateway' || rt.kind === 'gateway'
      ? cfg.baseUrl
      : rt.kind === 'direct'
        ? `direct · ${rt.provider.label}`
        : rt.kind === 'openrouter'
          ? 'via OpenRouter'
          : 'needs a provider key';

  useEffect(() => {
    if (transport === 'gateway') gatewayHealth(cfg.baseUrl).then(setProviders);
    else setProviders(null);
  }, [cfg.baseUrl, transport]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages]);

  const send = async () => {
    const text = input.trim();
    if (!text || busy) return;
    setErr('');
    setInput('');
    const next: ChatMessage[] = [...messages, { role: 'user', content: text }];
    setMessages([...next, { role: 'assistant', content: '' }]);
    setBusy(true);
    abortRef.current = new AbortController();
    try {
      await streamChat(cfg, next, (delta) => {
        setMessages((m) => {
          const copy = [...m];
          copy[copy.length - 1] = { role: 'assistant', content: copy[copy.length - 1].content + delta };
          return copy;
        });
      }, abortRef.current.signal);
    } catch (e) {
      setErr(String((e as Error).message ?? e));
      setMessages((m) => m.slice(0, -1)); // drop the empty assistant bubble
    } finally {
      setBusy(false);
    }
  };

  const updateModel = (model: string) => {
    const c = { ...cfg, model };
    setCfg(c);
    setChatConfig(c);
  };
  const updateBase = (baseUrl: string) => {
    const c = { ...cfg, baseUrl };
    setCfg(c);
    setChatConfig(c);
  };

  return (
    <div
      className="flex flex-col px-4 pb-2"
      style={{ minHeight: 'calc(100dvh - var(--tab-h) - 96px)' }}
    >
      {/* Header: model + gateway */}
      <div className="glass mb-2 flex items-center gap-2 px-3 py-2">
        <select
          value={cfg.model}
          onChange={(e) => updateModel(e.target.value)}
          className="mono rounded-md bg-[var(--panel-solid)] px-2 py-1 text-[11px] text-[var(--ink)]"
        >
          {modelsFor(cfg).map((m) => (
            <option key={m} value={m}>{m === 'auto' ? 'Auto · any model (no main provider)' : m}</option>
          ))}
        </select>
        <div className="mono flex-1 truncate text-[9px] text-[var(--ink-faint)]">
          {transportLabel}
        </div>
        <button
          onClick={() => navigate('/models')}
          className="mono shrink-0 text-[9px] text-[var(--octa-glow)]"
        >
          Models →
        </button>
        <span
          className="h-2 w-2 rounded-full"
          title={
            ready
              ? transport === 'server'
                ? 'hosted server chat · keys held on the server'
                : transportLabel
              : transport === 'direct'
                ? 'add a provider or OpenRouter key in Settings'
                : 'gateway offline'
          }
          style={{ background: ready ? 'var(--state-running)' : 'var(--ink-faint)' }}
        />
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="scroll-area flex-1">
        {messages.length === 0 ? (
          <div className="grid h-full place-items-center px-6 text-center">
            <div>
              <div className="text-[13px] font-semibold">Unified provider chat</div>
              {/* Three honest paths, no main provider, no fabricated output:
                  1. hosted server (this app's /api/chat, keys held server-side)
                  2. bring-your-own key (browser-direct via your own key/OpenRouter)
                  3. your gateway (the optional local MUSE provider gateway). */}
              {transport === 'server' ? (
                <div className="mt-1 text-[11px] leading-snug text-[var(--ink-dim)]">
                  <b className="text-[var(--ink)]">Hosted server chat</b> — runs through this app's own server,
                  with provider keys held on the server (never in your browser). Or{' '}
                  <b className="text-[var(--ink)]">bring your own key</b> in Settings → Credentials to chat
                  browser-direct, or point chat at <b className="text-[var(--ink)]">your gateway</b> below.{' '}
                  <button onClick={() => navigate('/models')} className="underline" style={{ color: 'var(--octa-glow)' }}>Browse all models →</button>
                </div>
              ) : transport === 'direct' ? (
                <div className="mt-1 text-[11px] leading-snug text-[var(--ink-dim)]">
                  <b className="text-[var(--ink)]">Bring your own key</b> — direct from this app,{' '}
                  <b className="text-[var(--ink)]">any of 300+ models across every provider</b>, no main provider,
                  through your own keys or OpenRouter. <b className="text-[var(--ink)]">No server, no terminal.</b>{' '}
                  The other honest paths are <b className="text-[var(--ink)]">hosted server chat</b> and{' '}
                  <b className="text-[var(--ink)]">your gateway</b>.{' '}
                  <button onClick={() => navigate('/models')} className="underline" style={{ color: 'var(--octa-glow)' }}>Browse all models →</button>
                </div>
              ) : (
                <div className="mt-1 text-[11px] leading-snug text-[var(--ink-dim)]">
                  Using <b className="text-[var(--ink)]">your gateway</b> (the local MUSE provider gateway). The
                  other honest paths: <b className="text-[var(--ink)]">hosted server chat</b>, or{' '}
                  <b className="text-[var(--ink)]">bring your own key</b> — paste an{' '}
                  <b className="text-[var(--ink)]">OpenRouter key</b> in Settings → Credentials and chat works
                  instantly with no gateway at all.
                </div>
              )}
              {!ready && (
                <div className="mono mt-3 text-[10px] text-[var(--state-auth)]">
                  {transport === 'direct' ? 'Add an OpenRouter key in Settings → Credentials' : `Gateway not reachable at ${cfg.baseUrl}`}
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-2.5 py-2">
            {messages.map((m, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                className={`max-w-[85%] rounded-2xl px-3 py-2 text-[13px] leading-relaxed ${m.role === 'user' ? 'self-end' : 'self-start'}`}
                style={{
                  background: m.role === 'user' ? 'color-mix(in oklab, var(--octa-glow) 18%, transparent)' : 'var(--panel)',
                  border: '1px solid var(--hairline)',
                }}
              >
                {m.content || (busy && i === messages.length - 1 ? '▋' : '')}
              </motion.div>
            ))}
          </div>
        )}
      </div>

      {err && <div className="mono px-1 pb-1 text-[10px] text-[var(--state-error)]">{err}</div>}

      {/* Composer */}
      <div
        className="glass flex items-end gap-2 px-2.5 py-2"
        style={{ marginBottom: 'calc(env(safe-area-inset-bottom) + 4px)' }}
      >
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
          rows={1}
          placeholder="Message…"
          className="max-h-28 flex-1 resize-none bg-transparent px-1 py-1.5 text-[14px] text-[var(--ink)] outline-none"
        />
        {busy ? (
          <button onClick={() => abortRef.current?.abort()} className="rounded-full border border-[var(--hairline)] px-3 py-1.5 text-[12px]">
            Stop
          </button>
        ) : (
          <button
            onClick={send}
            disabled={!input.trim()}
            aria-label="Send"
            className="grid h-9 w-9 place-items-center rounded-full text-black disabled:opacity-30"
            style={{ background: 'var(--octa-glow)' }}
          >
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 2 11 13M22 2l-7 20-4-9-9-4 20-7z" /></svg>
          </button>
        )}
      </div>

      {/* Gateway URL (collapsed control) */}
      <details className="px-1 pb-2">
        <summary className="mono cursor-pointer text-[9px] text-[var(--ink-faint)]">gateway settings</summary>
        <input
          value={cfg.baseUrl}
          onChange={(e) => updateBase(e.target.value)}
          className="mono mt-1 w-full rounded-md border border-[var(--hairline)] bg-[var(--panel-solid)] px-2 py-1.5 text-[11px] text-[var(--ink)]"
        />
      </details>
    </div>
  );
}
