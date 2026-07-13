import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { cockpit } from '@/adapters/cockpit';
import { useLinkState } from '@/lib/health';
import { routeForPath } from '@/universe/catalog';
import { UniversePage } from '@/universe/components/UniversePage';

// Share-target handler ("Send to M.U.S.E."). The OS routes shared text/links to
// /share?title=&text=&url=; the user composes it into an orchestrated goal.
export default function SharePage() {
  const navigate = useNavigate();
  const [text, setText] = useState('');
  const [msg, setMsg] = useState('');
  const [busy, setBusy] = useState(false);
  const connected = useLinkState() === 'gateway';
  const route = routeForPath('/share');

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
    const jobId = r && ((r as { id?: string; job_id?: string }).id ?? (r as { job_id?: string }).job_id);
    setMsg(jobId ? `Gateway acknowledged job ${jobId}` : r ? 'Gateway acknowledged the request; no job ID was reported.' : 'The gateway did not acknowledge the request.');
  };

  return (
    <UniversePage
      route={route}
      eyebrow="Signal broadcast"
      title="Share"
      description="OS share-target and clipboard handoff into a live Muse orchestration goal. Requires a reachable gateway — nothing is queued locally as pretend success."
    >
      <section className="universe-panel">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={7}
          className="w-full resize-none rounded-md border border-[var(--hairline)] bg-[var(--panel-solid)] px-2.5 py-2 text-[13px] text-[var(--ink)]"
          placeholder="Shared content…"
        />
        <div className="mt-3 flex gap-2">
          <button onClick={send} disabled={!text.trim() || busy || !connected} className="universe-button universe-button--primary flex-1 disabled:cursor-not-allowed disabled:opacity-40">
            {busy ? 'Sending…' : 'Orchestrate as a goal'}
          </button>
          <button onClick={() => navigate('/')} className="universe-button">
            Cancel
          </button>
        </div>
        {!connected && <div className="mono mt-3 text-[11px] text-[var(--ink-faint)]">A reachable Muse gateway is required to dispatch this goal.</div>}
        {msg && <div className="mono mt-3 text-[11px]" style={{ color: 'var(--ring-1)' }}>{msg}</div>}
      </section>
    </UniversePage>
  );
}
