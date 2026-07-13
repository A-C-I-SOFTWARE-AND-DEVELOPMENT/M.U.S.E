import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { Capability } from '@/lib/capabilities';
import { cockpit } from '@/adapters/cockpit';
import { useLinkState } from '@/lib/health';

interface Props {
  capability: Capability | null;
  onClose: () => void;
}

const REPO = 'https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/M.U.S.E/blob/main/';

function GatewayBadge() {
  const connected = useLinkState() === 'gateway';
  return connected ? (
    <span className="mono rounded-full px-2 py-0.5 text-[9px]" style={{ background: 'rgba(52,229,200,0.16)', color: 'var(--state-running)' }}>
      gateway connected
    </span>
  ) : (
    <span className="mono rounded-full px-2 py-0.5 text-[9px]" style={{ background: 'var(--hairline)', color: 'var(--ink-dim)' }}>
      requires gateway
    </span>
  );
}

function Json({ data }: { data: unknown }) {
  const connected = useLinkState() === 'gateway';
  if (data == null)
    return (
      <div className="glass px-3 py-4 text-center text-[11px] text-[var(--ink-dim)]">
        {connected ? 'The gateway returned no data' : 'A reachable gateway is required for live data'}
      </div>
    );
  return (
    <pre className="mono max-h-[40vh] overflow-auto rounded-md border border-[var(--hairline)] bg-[var(--panel-solid)] p-2.5 text-[10px] leading-relaxed text-[var(--ink-dim)]">
      {JSON.stringify(data, null, 2)}
    </pre>
  );
}

/** Read-only endpoint panel: fetch on open, pretty-print, refresh. */
function Fetcher({ label, load }: { label: string; load: () => Promise<unknown> }) {
  const [data, setData] = useState<unknown>(undefined);
  const [loading, setLoading] = useState(true);
  const connected = useLinkState() === 'gateway';
  const run = () => {
    if (!connected) {
      setData(undefined);
      setLoading(false);
      return;
    }
    setLoading(true);
    load().then((d) => {
      setData(d);
      setLoading(false);
    });
  };
  useEffect(() => { run(); /* eslint-disable-next-line */ }, [connected]);
  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <span className="hud-label">{label}</span>
        <button onClick={run} disabled={!connected} className="mono text-[10px] text-[var(--octa-glow)] disabled:cursor-not-allowed disabled:opacity-40">↻ refresh</button>
      </div>
      {loading ? <div className="py-4 text-center text-[11px] text-[var(--ink-dim)]">Loading…</div> : <Json data={data} />}
    </div>
  );
}

function QueryPanel({
  placeholder,
  run,
}: {
  placeholder: string;
  run: (q: string) => Promise<unknown>;
}) {
  const [q, setQ] = useState('');
  const [data, setData] = useState<unknown>(undefined);
  const [busy, setBusy] = useState(false);
  const connected = useLinkState() === 'gateway';
  const go = async () => {
    if (!connected) return;
    setBusy(true);
    setData(await run(q));
    setBusy(false);
  };
  return (
    <div className="flex flex-col gap-2">
      <div className="flex gap-2">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && go()}
          placeholder={placeholder}
          className="flex-1 rounded-md border border-[var(--hairline)] bg-[var(--panel-solid)] px-2.5 py-2 text-[12px] text-[var(--ink)]"
        />
        <button onClick={go} disabled={busy || !connected || !q.trim()} className="rounded-md px-3 py-2 text-[12px] font-semibold text-black disabled:cursor-not-allowed disabled:opacity-40" style={{ background: 'var(--octa-glow)' }}>
          {busy ? '…' : 'Run'}
        </button>
      </div>
      {!connected && <div className="text-[10px] text-[var(--ink-faint)]">Connect a reachable gateway to run this query.</div>}
      {data !== undefined && <Json data={data} />}
    </div>
  );
}

const MODES = [
  { k: 'companion', d: 'Warm, conversational thinking partner.' },
  { k: 'strategy', d: 'Long-horizon planning and trade-offs.' },
  { k: 'critic', d: 'Adversarial review of weak ideas.' },
  { k: 'operator', d: 'Run jobs, drive tools, execute.' },
  { k: 'builder', d: 'Implementation and PR handoff.' },
  { k: 'voice', d: 'Hands-free capture, driving mode.' },
];

const COMMANDS = [
  '/orchestrate <goal>', '/swarm <goal>', '/orchestrator status', '/profiles',
  '/jarvis', '/companion', '/strategy', '/critic', '/operator', '/builder', '/voice',
  '/model [provider:model]', '/personality [name]', '/packetize', '/memory-tree search',
  '/research', '/model-scorecard', '/owner-brief', '/reload-skills', '/new', '/reset',
];

function PanelBody({ cap }: { cap: Capability }) {
  const panel = cap.surface.kind === 'panel' ? cap.surface.panel : 'info';
  const [emergencyMsg, setEmergencyMsg] = useState('');
  const [mode, setMode] = useState('companion');
  const [goal, setGoal] = useState('');
  const [jobMsg, setJobMsg] = useState('');
  const [scope, setScope] = useState('local');
  const connected = useLinkState() === 'gateway';

  switch (panel) {
    case 'emergency':
      return (
        <div className="flex flex-col gap-3">
          <p className="text-[12px] text-[var(--ink-dim)]">
            Immediately halt all autonomous work. Read-only monitors keep running; in-flight
            jobs are paused and require explicit resume.
          </p>
          <button
            onClick={async () => {
              const r = await cockpit.emergencyStop();
              setEmergencyMsg(r ? 'The gateway acknowledged the emergency-stop request.' : connected ? 'The gateway did not acknowledge the request.' : 'No gateway connected.');
            }}
            disabled={!connected}
            className="rounded-md px-3 py-3 text-[13px] font-bold text-white disabled:cursor-not-allowed disabled:opacity-40"
            style={{ background: 'var(--state-error)' }}
          >
            ⏹ Engage emergency stop
          </button>
          {emergencyMsg && <div className="mono text-[11px] text-[var(--ink-dim)]">{emergencyMsg}</div>}
        </div>
      );

    case 'approvals':
      return <ApprovalsPanel />;

    case 'autonomy':
      return (
        <div className="flex flex-col gap-2">
          <Fetcher label="Autonomy state" load={() => cockpit.autonomy()} />
          <div className="flex gap-2">
            {['B0', 'B1', 'B2', 'B3'].map((b) => (
              <button key={b} onClick={() => cockpit.setAutonomy(b)} disabled={!connected} className="flex-1 rounded-md border border-[var(--hairline)] py-2 text-[11px] font-medium disabled:cursor-not-allowed disabled:opacity-40">
                {b}
              </button>
            ))}
          </div>
          <p className="text-[10px] text-[var(--ink-faint)]">Higher bands auto-approve only local friction; owner gates are never weakened.</p>
        </div>
      );

    case 'orchestrate':
      return (
        <div className="flex flex-col gap-3">
          <textarea
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            placeholder="Describe a goal — e.g. “Audit this repo and open a hardening PR”"
            rows={3}
            className="rounded-md border border-[var(--hairline)] bg-[var(--panel-solid)] px-2.5 py-2 text-[12px] text-[var(--ink)]"
          />
          <button
            onClick={async () => {
              const r = await cockpit.orchestrate(goal);
              const jobId = r && ((r as any).id ?? (r as any).job_id);
              setJobMsg(jobId ? `Gateway acknowledged job ${jobId}` : r ? 'Gateway acknowledged the request; no job ID was reported.' : connected ? 'The gateway did not acknowledge the request.' : 'No gateway connected.');
            }}
            disabled={!goal.trim() || !connected}
            className="rounded-md px-3 py-2.5 text-[12px] font-semibold text-black disabled:cursor-not-allowed disabled:opacity-40"
            style={{ background: 'var(--octa-glow)' }}
          >
            Orchestrate → Goal to PR
          </button>
          {jobMsg && <div className="mono text-[11px]" style={{ color: 'var(--octa-glow)' }}>{jobMsg}</div>}
          <Fetcher label="Active jobs" load={() => cockpit.jobs()} />
        </div>
      );

    case 'modes':
      return (
        <div className="flex flex-col gap-2">
          {MODES.map((m) => (
            <button
              key={m.k}
              onClick={() => setMode(m.k)}
              className="flex items-center justify-between rounded-md border px-3 py-2 text-left"
              style={{ borderColor: mode === m.k ? 'var(--octa-glow)' : 'var(--hairline)' }}
            >
              <div>
                <div className="text-[12px] font-semibold capitalize">{m.k}</div>
                <div className="text-[10px] text-[var(--ink-dim)]">{m.d}</div>
              </div>
              {mode === m.k && <span className="mono text-[10px]" style={{ color: 'var(--octa-glow)' }}>active</span>}
            </button>
          ))}
          <p className="text-[10px] text-[var(--ink-faint)]">Pin a mode in any session with the matching slash command (e.g. /builder).</p>
        </div>
      );

    case 'memory':
      return <QueryPanel placeholder="Search the Memory Tree…" run={(q) => cockpit.memorySearch(q)} />;
    case 'packetize':
      return <QueryPanel placeholder="Plain-English coding request → work packet" run={(q) => cockpit.rawPost('/coding/plan', { request: q })} />;
    case 'evidence':
      return <QueryPanel placeholder="Search evidence (BM25 + memory hybrid)…" run={(q) => cockpit.evidenceSearch(q)} />;
    case 'graph':
      return (
        <div className="flex flex-col gap-2">
          <div className="flex gap-2">
            {['local', 'global', 'coding'].map((s) => (
              <button key={s} onClick={() => setScope(s)} className="flex-1 rounded-md border py-1.5 text-[11px]" style={{ borderColor: scope === s ? 'var(--octa-glow)' : 'var(--hairline)', color: scope === s ? 'var(--octa-glow)' : 'var(--ink)' }}>
                {s}
              </button>
            ))}
          </div>
          <QueryPanel placeholder={`GraphRAG ${scope} query…`} run={(q) => cockpit.graphQuery(q, scope)} />
        </div>
      );

    case 'research':
      return <Fetcher label="Research Vault" load={() => cockpit.research()} />;
    case 'modelroutes':
      return <Fetcher label="Model routes & scorecards" load={() => cockpit.modelRoutes()} />;
    case 'learning':
      return <Fetcher label="Learning dataset" load={() => cockpit.learning()} />;
    case 'proposals':
      return <Fetcher label="Self-improvement proposals" load={() => cockpit.proposals()} />;
    case 'audit':
      return <Fetcher label="Evidence ledger (verify_chain)" load={() => cockpit.audit()} />;
    case 'skills':
      return <Fetcher label="Skills" load={() => cockpit.skills()} />;
    case 'runtime':
      return <Fetcher label="Runtime status" load={() => cockpit.runtimeStatus()} />;

    case 'commands':
      return (
        <div className="grid grid-cols-1 gap-1.5">
          {COMMANDS.map((c) => (
            <div key={c} className="mono rounded-md border border-[var(--hairline)] px-2.5 py-1.5 text-[11px] text-[var(--ink)]">{c}</div>
          ))}
          <p className="mt-1 text-[10px] text-[var(--ink-faint)]">Run these in any MUSE gateway DM or the `muse` REPL. /orchestrate is also wired in the Orchestration card.</p>
        </div>
      );

    case 'info':
    default:
      return (
        <div className="flex flex-col gap-2">
          <p className="text-[12px] leading-relaxed text-[var(--ink-dim)]">{cap.blurb}</p>
          {cap.doc && (
            <a href={`${REPO}${cap.doc}`} target="_blank" rel="noopener noreferrer" className="mono text-[11px]" style={{ color: 'var(--octa-glow)' }}>
              Open documentation ↗
            </a>
          )}
        </div>
      );
  }
}

function ApprovalsPanel() {
  const [list, setList] = useState<any[] | null>(null);
  const [phrase, setPhrase] = useState('');
  const connected = useLinkState() === 'gateway';
  const load = () => connected ? cockpit.approvals().then((r: any) => setList(Array.isArray(r) ? r : (r?.approvals ?? []))) : Promise.resolve(setList(null));
  useEffect(() => { void load(); }, [connected]);
  const exact = phrase.trim() === 'Yes, with authorization.';
  return (
    <div className="flex flex-col gap-2">
      {!list || list.length === 0 ? (
        <div className="glass px-3 py-4 text-center text-[11px] text-[var(--ink-dim)]">
          {connected ? 'No pending owner-gated actions were reported' : 'Requires a reachable gateway'}
        </div>
      ) : (
        <>
          {list.map((a) => (
            <div key={a.id} className="glass px-3 py-2.5">
              <div className="text-[12px] font-medium">{a.title ?? a.action ?? a.id}</div>
              {a.risk && <div className="mono text-[9px] text-[var(--state-auth)]">{a.risk}</div>}
              <div className="mt-2 flex gap-2">
                <button onClick={() => cockpit.approve(a.id, phrase).then(load)} disabled={!exact} className="rounded-md px-2.5 py-1 text-[11px] font-semibold text-black disabled:opacity-40" style={{ background: 'var(--state-running)' }}>Approve</button>
                <button onClick={() => cockpit.deny(a.id).then(load)} className="rounded-md border border-[var(--hairline)] px-2.5 py-1 text-[11px]">Deny</button>
              </div>
            </div>
          ))}
          <input
            value={phrase}
            onChange={(e) => setPhrase(e.target.value)}
            placeholder="Type: Yes, with authorization."
            className="rounded-md border px-2.5 py-2 text-[12px]"
            style={{ borderColor: exact ? 'var(--state-running)' : 'var(--hairline)', background: 'var(--panel-solid)', color: 'var(--ink)' }}
          />
          <p className="text-[10px] text-[var(--ink-faint)]">The exact owner phrase unlocks Approve — owner control by construction.</p>
        </>
      )}
    </div>
  );
}

export function CapabilityDrawer({ capability, onClose }: Props) {
  return (
    <AnimatePresence>
      {capability && (
        <>
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose} className="fixed inset-0 z-40 bg-black/60" />
          <motion.div
            initial={{ y: '100%' }}
            animate={{ y: 0 }}
            exit={{ y: '100%' }}
            transition={{ type: 'spring', stiffness: 380, damping: 38 }}
            className="fixed inset-x-0 bottom-0 z-50 max-h-[86vh] overflow-y-auto rounded-t-2xl border-t border-[var(--hairline)] bg-[var(--bg-elev)] px-4 pb-8 pt-3"
            style={{ paddingBottom: 'calc(env(safe-area-inset-bottom) + 24px)' }}
          >
            <div className="mx-auto mb-3 h-1 w-10 rounded-full bg-[var(--hairline-strong)]" />
            <div className="mb-3 flex items-start justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <span className="h-2.5 w-2.5 rounded-full" style={{ background: capability.accent }} />
                  <h2 className="text-[16px] font-bold">{capability.title}</h2>
                </div>
                {capability.endpoint && <div className="mono mt-1 text-[9px] text-[var(--ink-faint)]">{capability.endpoint}</div>}
              </div>
              <div className="flex items-center gap-2">
                <GatewayBadge />
                <button onClick={onClose} className="grid h-7 w-7 place-items-center rounded-full border border-[var(--hairline)] text-[var(--ink-dim)]">✕</button>
              </div>
            </div>
            <PanelBody cap={capability} />
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
