import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  fetchSecondBrainStatus,
  retrieveSecondBrain,
  type SecondBrainResult,
  type SecondBrainStatus,
} from '@/lib/secondBrain';
import { museBase } from '@/lib/config';

export default function SecondBrainPage() {
  const navigate = useNavigate();
  const [status, setStatus] = useState<SecondBrainStatus | null>(null);
  const [statusLoading, setStatusLoading] = useState(false);
  const [q, setQ] = useState('');
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<SecondBrainResult | null>(null);

  const connected = !!museBase();

  useEffect(() => {
    if (!connected) return;
    let alive = true;
    setStatusLoading(true);
    fetchSecondBrainStatus()
      .then((s) => { if (alive) setStatus(s); })
      .finally(() => { if (alive) setStatusLoading(false); });
    return () => { alive = false; };
  }, [connected]);

  const run = async () => {
    const query = q.trim();
    if (!query || busy) return;
    setBusy(true);
    try {
      setResult(await retrieveSecondBrain(query));
    } finally {
      setBusy(false);
    }
  };

  const dot = (on: boolean) => (on ? 'var(--state-running)' : 'var(--ink-faint)');

  return (
    <div className="px-4 pb-6">
      <div className="glass mb-3 px-3 py-2.5">
        <div className="text-[13px] font-semibold">Second Brain</div>
        <div className="mono text-[10px] text-[var(--ink-dim)]">
          Hybrid vector + keyword retrieval — augments, never replaces, native recall.
        </div>
      </div>

      {!connected ? (
        <div className="glass px-4 py-8 text-center">
          <div className="text-[12px] text-[var(--ink-dim)]">No gateway connected</div>
          <div className="mt-1 text-[10px] text-[var(--ink-faint)]">
            The Second Brain runs on your MUSE gateway. Connect one to query it.
          </div>
          <button
            onClick={() => navigate('/settings')}
            className="mt-3 rounded-md px-3 py-1.5 text-[11px] font-semibold text-black"
            style={{ background: 'var(--octa-glow)' }}
          >
            Open Settings
          </button>
        </div>
      ) : (
        <>
          {/* Status banner */}
          {statusLoading && !status ? (
            <div className="glass mb-3 px-3 py-2 mono text-[10px] text-[var(--ink-dim)]">Reading Second Brain status…</div>
          ) : status?.error ? (
            <div className="glass mono mb-3 px-3 py-2 text-[10px] text-[var(--state-error)]">{status.error}</div>
          ) : (
            <div className="glass mb-3 flex items-center gap-3 px-3 py-2">
              <span className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full" style={{ background: dot(!!status?.enabled) }} />
                <span className="mono text-[10px] text-[var(--ink-dim)]">
                  {status?.enabled ? 'enabled' : 'disabled'}
                </span>
              </span>
              <span className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full" style={{ background: dot(!!status?.available) }} />
                <span className="mono text-[10px] text-[var(--ink-dim)]">
                  {status?.available ? 'module ready' : 'unavailable'}
                </span>
              </span>
              {status?.backend && (
                <span className="mono text-[10px] text-[var(--ink-faint)]">backend: {status.backend}</span>
              )}
            </div>
          )}

          {status && !status.error && !status.enabled && (
            <div className="mono mb-3 rounded-md px-3 py-2 text-[10px] text-[var(--state-auth)]" style={{ border: '1px solid var(--hairline)' }}>
              Disabled on the gateway. Set <b className="text-[var(--ink)]">MUSE_SECOND_BRAIN=1</b> to enable retrieval.
            </div>
          )}

          {/* Query */}
          <div className="mb-3 flex gap-2">
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') void run(); }}
              placeholder="Ask the Second Brain…"
              className="flex-1 rounded-md border border-[var(--hairline)] bg-[var(--panel-solid)] px-3 py-2 text-[12px] text-[var(--ink)]"
            />
            <button
              onClick={() => void run()}
              disabled={busy || !q.trim()}
              className="rounded-md px-3 py-2 text-[11px] font-semibold text-black disabled:opacity-40"
              style={{ background: 'var(--octa-glow)' }}
            >
              {busy ? '…' : 'Retrieve'}
            </button>
          </div>

          {/* Result */}
          {result && (
            <div className="glass px-3 py-3">
              {result.error ? (
                <div className="mono text-[11px] text-[var(--state-error)]">{result.error}</div>
              ) : result.blocks > 0 ? (
                <>
                  <div className="mono mb-2 text-[10px] text-[var(--ink-faint)]">
                    {result.blocks} block{result.blocks === 1 ? '' : 's'} · backend {result.backendReady ? 'ready' : 'empty'}
                  </div>
                  <pre className="mono whitespace-pre-wrap break-words text-[11px] leading-relaxed text-[var(--ink)]">{result.text}</pre>
                </>
              ) : (
                <div className="mono text-[11px] text-[var(--ink-dim)]">
                  {result.enabled
                    ? result.backendReady
                      ? 'No matching context in the Second Brain yet.'
                      : 'Backend not ready — configure SECOND_BRAIN_* (or use the in-memory backend) on the gateway.'
                    : 'Second Brain is disabled on the gateway.'}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
