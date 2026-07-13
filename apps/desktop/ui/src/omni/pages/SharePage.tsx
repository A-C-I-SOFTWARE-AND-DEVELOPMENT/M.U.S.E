import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { cockpit } from '@/adapters/cockpit';
import { useLinkState } from '@/lib/health';

// Share-target handler ("Send to M.U.S.E."). The OS routes shared text/links to
// /share?title=&text=&url=; the user composes it into an orchestrated goal.
export default function SharePage() {
  const navigate = useNavigate();
  const [text, setText] = useState('');
  const [msg, setMsg] = useState('');
  const [busy, setBusy] = useState(false);
  const connected = useLinkState() === 'gateway';

  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    const parts = [p.get('title'), p.get('text'), p.get('url')].filter(Boolean);
    setText(parts.join('\n'));
  }, []);

  const send = async () => {
    if (!connected) return;
    setBusy(true);
    const r = await cockpit.orchestrate(text);
    setBusy(false);
    const jobId = r && ((r as any).id ?? (r as any).job_id);
    setMsg(jobId ? `Gateway acknowledged job ${jobId}` : r ? 'Gateway acknowledged the request; no job ID was reported.' : 'The gateway did not acknowledge the request.');
  };

  return (
    <div className="px-4 pb-6 pt-2">
      <div className="hud-label mb-2">Send to M.U.S.E.</div>
      <div className="glass px-3 py-3">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={6}
          className="w-full rounded-md border border-[var(--hairline)] bg-[var(--panel-solid)] px-2.5 py-2 text-[13px] text-[var(--ink)]"
          placeholder="Shared content…"
        />
        <div className="mt-2 flex gap-2">
          <button onClick={send} disabled={!text.trim() || busy || !connected} className="flex-1 rounded-md px-3 py-2.5 text-[12px] font-semibold text-black disabled:cursor-not-allowed disabled:opacity-40" style={{ background: 'var(--octa-glow)' }}>
            {busy ? 'Sending…' : 'Orchestrate as a goal'}
          </button>
          <button onClick={() => navigate('/')} className="rounded-md border border-[var(--hairline)] px-3 py-2.5 text-[12px]">
            Cancel
          </button>
        </div>
        {!connected && <div className="mono mt-2 text-[11px] text-[var(--ink-faint)]">A reachable gateway is required to dispatch this goal.</div>}
        {msg && <div className="mono mt-2 text-[11px]" style={{ color: 'var(--octa-glow)' }}>{msg}</div>}
      </div>
    </div>
  );
}
