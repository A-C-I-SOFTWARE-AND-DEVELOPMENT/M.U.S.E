import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { cockpit, cockpitConfigured, type CockpitJob } from '@/adapters/cockpit';
import { checkBudget, concurrencyCeiling, planFanout, reduceTiers, type SiloedTask } from '@/lib/fleet';

export default function FleetPage() {
  const navigate = useNavigate();
  const [goal, setGoal] = useState('');
  const [count, setCount] = useState(64);
  const [capUsd, setCapUsd] = useState(5);
  const [mode, setMode] = useState<'local' | 'cloud' | 'hybrid'>('hybrid');
  const [jobs, setJobs] = useState<CockpitJob[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [msg, setMsg] = useState('');
  const connected = cockpitConfigured();

  const refresh = () =>
    cockpit
      .jobs()
      .then((r: any) => setJobs(Array.isArray(r) ? r : r?.jobs ?? []))
      .finally(() => setLoaded(true));
  useEffect(() => {
    refresh();
    const id = window.setInterval(refresh, 5000);
    return () => window.clearInterval(id);
  }, []);

  const ceiling = concurrencyCeiling(mode);
  const tasks: SiloedTask[] = Array.from({ length: count }, (_, i) => ({ id: `t${i}`, instruction: goal, timeoutSec: 60, verifier: 'schema' }));
  const plan = planFanout(goal, tasks, { concurrency: Math.min(256, ceiling.max), perTaskUsd: 0.002, perTaskSec: 20 });
  const budget = checkBudget(plan.estCostUsd, capUsd);
  const tiers = reduceTiers(count);

  const launch = async () => {
    if (!budget.allowed) return;
    const r = await cockpit.rawPost('/orchestrate', { goal, fanout: { count, concurrency: plan.concurrency, budgetUsd: capUsd, verifier: 'schema' } });
    setConfirming(false);
    setMsg(r ? `Fan-out submitted: ${count} siloed tasks` : cockpitConfigured() ? 'Submit failed' : 'Requires gateway + orchestrator (Hatchet)');
    refresh();
  };

  const killAll = async () => {
    await cockpit.emergencyStop();
    setMsg('Emergency stop engaged.');
    refresh();
  };

  return (
    <div className="px-4 pb-6">
      <div className="glass mb-3 flex items-center justify-between px-3 py-2.5">
        <div>
          <div className="text-[13px] font-semibold">The Fleet</div>
          <div className="mono text-[10px] text-[var(--ink-dim)]">massive 1-minute siloed fan-out</div>
        </div>
        <button onClick={killAll} className="rounded-md px-3 py-1.5 text-[11px] font-bold text-white" style={{ background: 'var(--state-error)' }}>⏹ Kill all</button>
      </div>

      {/* Launcher */}
      <div className="glass mb-3 px-3 py-3">
        <div className="hud-label mb-2">Launch fan-out</div>
        <textarea value={goal} onChange={(e) => setGoal(e.target.value)} rows={2} placeholder="Goal to decompose into N siloed tasks…" className="w-full resize-none rounded-md border border-[var(--hairline)] bg-[var(--panel-solid)] px-2.5 py-2 text-[13px] text-[var(--ink)]" />
        <div className="mt-2 grid grid-cols-3 gap-2">
          <label className="mono text-[9px] text-[var(--ink-dim)]">tasks
            <input type="number" min={1} max={5000} value={count} onChange={(e) => setCount(Math.max(1, +e.target.value))} className="mt-0.5 w-full rounded-md border border-[var(--hairline)] bg-[var(--panel-solid)] px-2 py-1 text-[12px] text-[var(--ink)]" />
          </label>
          <label className="mono text-[9px] text-[var(--ink-dim)]">budget $
            <input type="number" min={0} step={0.5} value={capUsd} onChange={(e) => setCapUsd(Math.max(0, +e.target.value))} className="mt-0.5 w-full rounded-md border border-[var(--hairline)] bg-[var(--panel-solid)] px-2 py-1 text-[12px] text-[var(--ink)]" />
          </label>
          <label className="mono text-[9px] text-[var(--ink-dim)]">mode
            <select value={mode} onChange={(e) => setMode(e.target.value as any)} className="mt-0.5 w-full rounded-md border border-[var(--hairline)] bg-[var(--panel-solid)] px-1 py-1 text-[12px] text-[var(--ink)]">
              <option value="local">local</option><option value="cloud">cloud</option><option value="hybrid">hybrid</option>
            </select>
          </label>
        </div>

        {/* Projected cost + honest ceiling */}
        <div className="mono mt-2 flex flex-wrap gap-x-3 gap-y-0.5 text-[10px] text-[var(--ink-dim)]">
          <span>≈ ${plan.estCostUsd.toFixed(2)}</span>
          <span>≈ {plan.estWallclockSec}s</span>
          <span>{plan.concurrency} concurrent</span>
          <span>reduce {tiers.join('→')}</span>
        </div>
        <div className="mono mt-1 text-[9px] text-[var(--ink-faint)]">{ceiling.note}</div>
        {count > ceiling.max && <div className="mono mt-1 text-[9px] text-[var(--state-auth)]">{count} &gt; {ceiling.max} max for {mode} — switch to cloud/hybrid.</div>}

        {!budget.allowed && <div className="mono mt-1 text-[10px] text-[var(--state-error)]">{budget.reason}</div>}

        {!confirming ? (
          <button onClick={() => setConfirming(true)} disabled={!goal.trim() || !budget.allowed} className="mt-2 w-full rounded-md px-3 py-2.5 text-[12px] font-semibold text-black disabled:opacity-40" style={{ background: 'var(--octa-glow)' }}>
            Review &amp; launch
          </button>
        ) : (
          <div className="mt-2 rounded-md border border-[var(--state-auth)] px-3 py-2.5">
            <div className="text-[11px] text-[var(--ink)]">Launch <b>{count}</b> tasks · projected <b>${plan.estCostUsd.toFixed(2)}</b> (cap ${capUsd})?</div>
            <div className="mt-2 flex gap-2">
              <button onClick={launch} className="flex-1 rounded-md py-1.5 text-[11px] font-semibold text-black" style={{ background: 'var(--octa-glow)' }}>Confirm launch</button>
              <button onClick={() => setConfirming(false)} className="rounded-md border border-[var(--hairline)] px-3 py-1.5 text-[11px]">Cancel</button>
            </div>
          </div>
        )}
        {msg && <div className="mono mt-2 text-[10px]" style={{ color: 'var(--octa-glow)' }}>{msg}</div>}
      </div>

      {/* Live grid + mirror link */}
      <div className="mb-2 flex items-center justify-between">
        <div className="hud-label">In-flight · {jobs.length}</div>
        <button onClick={() => navigate('/observatory')} className="mono text-[10px] text-[var(--octa-glow)]">live galaxy →</button>
      </div>
      {!loaded && connected ? (
        <div className="glass px-4 py-6 text-center">
          <div className="text-[12px] text-[var(--ink-dim)]">Mirroring live jobs…</div>
        </div>
      ) : jobs.length === 0 ? (
        <div className="glass px-4 py-6 text-center">
          <div className="text-[12px] text-[var(--ink-dim)]">{connected ? 'No jobs in flight' : 'Not connected'}</div>
          <div className="mt-1 text-[10px] text-[var(--ink-faint)]">{connected ? 'Launch a fan-out above.' : 'Requires gateway to mirror live jobs.'}</div>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          {jobs.slice(0, 60).map((j) => (
            <div key={j.id} className="glass px-2.5 py-2">
              <div className="mono truncate text-[10px] text-[var(--ink)]">{j.id}</div>
              <div className="mono text-[9px] text-[var(--ink-faint)]">{j.state ?? j.status ?? 'running'}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
