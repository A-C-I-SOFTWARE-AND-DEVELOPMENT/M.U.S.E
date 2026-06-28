import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { establishConnections, localGatewayBlockedByHttps, detectSameOriginGateway, type ConnectStep } from '@/lib/connect';
import { getConfig, getSecret, setSecret } from '@/lib/config';

// Paste-into-Termux one-liner that brings up a MUSE gateway on the phone and
// serves NEXUS same-origin at http://127.0.0.1:8765/nexus/.
const TERMUX_ONELINER =
  'curl -fsSL https://raw.githubusercontent.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/M.U.S.E/main/scripts/termux-nexus-gateway.sh | bash';

interface Props {
  open: boolean;
  onClose: () => void;
}

const STATUS_META: Record<ConnectStep['status'], { color: string; glyph: string }> = {
  pending: { color: 'var(--ink-faint)', glyph: '○' },
  running: { color: 'var(--octa-glow)', glyph: '◐' },
  ok: { color: 'var(--state-running)', glyph: '✓' },
  skip: { color: 'var(--ink-dim)', glyph: '–' },
  fail: { color: 'var(--state-error)', glyph: '✕' },
};

const OWNER_PHRASE = 'Yes, with authorization.';

export function ConnectWizard({ open, onClose }: Props) {
  const [baseUrl, setBaseUrl] = useState(getConfig().museBaseUrl);
  const [phrase, setPhrase] = useState('');
  const [withPush, setWithPush] = useState(true);
  const [orKey, setOrKey] = useState(getSecret('OPENROUTER_API_KEY'));
  const [orSaved, setOrSaved] = useState(false);
  const [steps, setSteps] = useState<ConnectStep[]>([]);
  const [running, setRunning] = useState(false);
  const [done, setDone] = useState(false);
  const [installEvt, setInstallEvt] = useState<any>(null);
  const [device, setDevice] = useState('');
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const handler = (e: Event) => {
      e.preventDefault();
      setInstallEvt(e);
    };
    window.addEventListener('beforeinstallprompt', handler);
    return () => window.removeEventListener('beforeinstallprompt', handler);
  }, []);

  // If NEXUS is being served BY a gateway (same origin — e.g. MUSE in Termux on
  // this phone serving /nexus/), detect it and connect automatically.
  useEffect(() => {
    if (!open) return;
    let alive = true;
    detectSameOriginGateway().then((origin) => {
      if (!alive || !origin) return;
      setDevice(origin);
      setBaseUrl(origin);
      if (!getConfig().museToken) void run(origin);
    });
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const copyCmd = async () => {
    try {
      await navigator.clipboard.writeText(TERMUX_ONELINER);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch { /* clipboard unavailable */ }
  };

  const run = async (overrideBase?: string) => {
    setRunning(true);
    setDone(false);
    const final = await establishConnections(
      { baseUrl: (overrideBase ?? baseUrl).trim() || undefined, ownerPhrase: phrase.trim() || OWNER_PHRASE, withPush },
      setSteps,
    );
    setRunning(false);
    setDone(true);
    if (final.find((s) => s.key === 'capabilities')?.status === 'ok') {
      // Connected — auto-dismiss shortly so the user lands in the live app.
      setTimeout(onClose, 1400);
    }
  };

  const installPwa = async () => {
    if (!installEvt) return;
    installEvt.prompt();
    await installEvt.userChoice;
    setInstallEvt(null);
  };

  const okCount = steps.filter((s) => s.status === 'ok').length;
  // Hosted over HTTPS with only a local http gateway → that gateway can't be
  // reached (mixed content). Surface this as "expected", not a failure.
  const hostedNoGateway = localGatewayBlockedByHttps(baseUrl);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-[60] flex flex-col bg-[var(--bg-base)]"
          style={{ paddingTop: 'env(safe-area-inset-top)' }}
        >
          <div className="scroll-area flex-1 px-5 py-6">
            <div className="mb-1 flex items-center gap-2.5">
              <div
                className="grid h-9 w-9 place-items-center rounded-lg text-[15px] font-bold text-black"
                style={{ background: 'linear-gradient(135deg, var(--acc-coding), var(--acc-creativity))' }}
              >
                N
              </div>
              <div>
                <div className="text-[17px] font-bold">Install & Connect</div>
                <div className="mono text-[10px] text-[var(--ink-dim)]">one click · autonomous bring-up</div>
              </div>
            </div>
            <p className="mt-3 text-[12px] leading-relaxed text-[var(--ink-dim)]">
              The fastest way — <b className="text-[var(--ink)]">no server, no terminal</b>: paste one
              OpenRouter key and chat + fusion work instantly, straight from this app (Claude, GPT,
              Gemini & 300+ models). The MUSE gateway is optional, for orchestration / memory / fleet.
            </p>

            {device && (
              <div className="mt-3 rounded-lg border px-3 py-2.5" style={{ borderColor: 'var(--state-running)', background: 'color-mix(in oklab, var(--state-running) 8%, transparent)' }}>
                <div className="text-[11px] font-semibold" style={{ color: 'var(--state-running)' }}>MUSE gateway detected on this device ✓</div>
                <div className="mono mt-1 text-[10px] text-[var(--ink-dim)]">{device} — connecting automatically…</div>
              </div>
            )}

            {hostedNoGateway && !device && (
              <div className="mt-3 rounded-lg border px-3 py-2.5" style={{ borderColor: 'var(--state-auth, #FFB020)', background: 'color-mix(in oklab, var(--state-auth, #FFB020) 8%, transparent)' }}>
                <div className="text-[11px] font-semibold" style={{ color: 'var(--state-auth, #FFB020)' }}>Running hosted — the local gateway is out of reach (that's normal)</div>
                <div className="mt-1 text-[10px] leading-relaxed text-[var(--ink-dim)]">
                  This page is served over HTTPS, so it can't reach a <span className="mono">http://localhost</span> MUSE
                  gateway (browsers block mixed content), and on a phone <span className="mono">localhost</span> is the phone.
                  <b className="text-[var(--ink)]"> Everything that doesn't need the gateway works right now</b> —
                  provider Chat, Models, Fusion (with your key), and the whole Repo mirror. Just tap
                  <b className="text-[var(--ink)]"> Enter NEXUS</b>.
                </div>
                <div className="mt-2 border-t border-[var(--hairline)] pt-2 text-[10px] leading-relaxed text-[var(--ink-dim)]">
                  <b className="text-[var(--ink)]">Want the entire MUSE on this phone?</b> Run a gateway right here in
                  <b className="text-[var(--ink)]"> Termux</b> — it serves NEXUS at <span className="mono">localhost:8765/nexus/</span>
                  (same origin, no tunnel). Paste this:
                  <div className="mono mt-1.5 flex items-start gap-2 rounded-md border border-[var(--hairline)] bg-[var(--panel-solid)] px-2 py-1.5">
                    <span className="min-w-0 flex-1 break-all text-[9.5px] text-[var(--ink)]">{TERMUX_ONELINER}</span>
                    <button onClick={copyCmd} className="shrink-0 rounded px-1.5 py-0.5 text-[9px] font-semibold text-black" style={{ background: 'var(--octa-glow)' }}>{copied ? 'Copied ✓' : 'Copy'}</button>
                  </div>
                  <span className="mt-1 block">Then open <span className="mono">http://127.0.0.1:8765/nexus/</span> on the phone — NEXUS auto-connects.</span>
                </div>
              </div>
            )}

            {/* Primary path: one key, no server */}
            <div className="glass mt-4 px-3 py-3" style={{ borderColor: orSaved ? 'var(--state-running)' : 'var(--hairline)' }}>
              <label className="hud-label">OpenRouter key — chat &amp; fusion, no gateway</label>
              <div className="mt-1.5 flex gap-2">
                <input
                  value={orKey}
                  onChange={(e) => { setOrKey(e.target.value); setOrSaved(false); }}
                  type="password"
                  placeholder="sk-or-…"
                  autoComplete="off"
                  className="flex-1 rounded-md border border-[var(--hairline)] bg-[var(--panel-solid)] px-3 py-2 text-[12px] text-[var(--ink)]"
                />
                <button
                  onClick={() => { setSecret('OPENROUTER_API_KEY', orKey.trim()); setOrSaved(true); }}
                  disabled={!orKey.trim()}
                  className="rounded-md px-3 py-2 text-[12px] font-semibold text-black disabled:opacity-40"
                  style={{ background: 'var(--octa-glow)' }}
                >
                  {orSaved ? 'Saved ✓' : 'Save'}
                </button>
              </div>
              <div className="mono mt-1.5 text-[9px] text-[var(--ink-faint)]">
                Get one at openrouter.ai/keys · stored encrypted on this device.
                {orSaved && <span style={{ color: 'var(--state-running)' }}> Done — open Chat.</span>}
              </div>
            </div>

            {/* Connect your M.U.S.E. — gateway URL + owner-phrase pairing,
                promoted to a top-level card (orchestration · memory · fleet). */}
            <div className="glass mt-4 px-3 py-3" style={{ borderColor: 'var(--hairline)' }}>
              <label className="hud-label">Connect your M.U.S.E. — orchestration · memory · fleet</label>
              <p className="mt-1 text-[10px] leading-relaxed text-[var(--ink-dim)]">
                Pair this device with your own MUSE gateway to unlock the cockpit: jobs, owner
                approvals, the Memory Tree, GraphRAG and the fleet. Optional — chat &amp; fusion
                already work above without it.
              </p>
              <div className="mt-2 flex flex-col gap-2.5">
                <label className="hud-label">Gateway URL (blank = auto-discover)</label>
                <input
                  value={baseUrl}
                  onChange={(e) => setBaseUrl(e.target.value)}
                  placeholder="http://127.0.0.1:8765"
                  className="rounded-md border border-[var(--hairline)] bg-[var(--panel-solid)] px-3 py-2 text-[12px] text-[var(--ink)]"
                />
                <label className="hud-label mt-1">Owner authorization phrase</label>
                <input
                  value={phrase}
                  onChange={(e) => setPhrase(e.target.value)}
                  placeholder={OWNER_PHRASE}
                  className="rounded-md border px-3 py-2 text-[12px] text-[var(--ink)]"
                  style={{ borderColor: phrase.trim() === OWNER_PHRASE ? 'var(--state-running)' : 'var(--hairline)', background: 'var(--panel-solid)' }}
                />
                <label className="mt-1 flex items-center gap-2 text-[11px] text-[var(--ink-dim)]">
                  <input type="checkbox" checked={withPush} onChange={(e) => setWithPush(e.target.checked)} />
                  Enable push notifications during connect
                </label>
              </div>
              {/* Mixed-content / HTTPS-tunnel guidance: a hosted https page can't
                  reach a http://localhost gateway. Surfaced here so the card is
                  self-explanatory wherever it renders. */}
              <p className="mono mt-2 border-t border-[var(--hairline)] pt-2 text-[9px] leading-relaxed text-[var(--ink-faint)]">
                Hosted over HTTPS? A <span className="text-[var(--ink-dim)]">http://localhost</span> gateway is
                blocked by mixed-content. Either run NEXUS same-origin from the gateway (Termux,
                <span className="text-[var(--ink-dim)]"> localhost:8765/nexus/</span>) or expose the gateway over
                HTTPS (a tunnel) and paste that <span className="text-[var(--ink-dim)]">https://</span> URL above —
                the per-account bearer then stays server-side via the relay.
              </p>
            </div>

            {/* Progress */}
            {steps.length > 0 && (
              <div className="glass mt-4 px-3 py-3">
                <div className="hud-label mb-2">Bring-up · {okCount}/{steps.length} connected</div>
                <div className="flex flex-col gap-1.5">
                  {steps.map((s) => {
                    const m = STATUS_META[s.status];
                    return (
                      <div key={s.key} className="flex items-center gap-2.5">
                        <motion.span
                          animate={s.status === 'running' ? { rotate: 360 } : { rotate: 0 }}
                          transition={s.status === 'running' ? { repeat: Infinity, duration: 1, ease: 'linear' } : {}}
                          className="mono w-4 text-center text-[12px]"
                          style={{ color: m.color }}
                        >
                          {m.glyph}
                        </motion.span>
                        <span className="w-[150px] shrink-0 text-[12px]">{s.label}</span>
                        <span className="mono flex-1 truncate text-[9px] text-[var(--ink-faint)]">{s.detail ?? ''}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {done && (
              <div className="mt-3 text-center text-[12px]" style={{ color: okCount >= 3 ? 'var(--state-running)' : 'var(--state-auth)' }}>
                {okCount >= 3 ? 'Connected. Entering NEXUS…' : 'Partial connection — review the steps above.'}
              </div>
            )}
          </div>

          {/* Actions */}
          <div
            className="flex flex-col gap-2 border-t border-[var(--hairline)] bg-[var(--bg-elev)] px-5 py-4"
            style={{ paddingBottom: 'calc(env(safe-area-inset-bottom) + 16px)' }}
          >
            {/* When hosted without a reachable gateway, entering NEXUS is the
                primary action (everything non-gateway works); connecting is secondary. */}
            {hostedNoGateway ? (
              <>
                <button
                  onClick={onClose}
                  className="w-full rounded-md px-3 py-3 text-[13px] font-bold text-black"
                  style={{ background: 'var(--octa-glow)' }}
                >
                  Enter NEXUS →
                </button>
                <div className="flex gap-2">
                  {installEvt && (
                    <button onClick={installPwa} className="flex-1 rounded-md border border-[var(--hairline)] px-3 py-2 text-[12px]">
                      Add to Home Screen
                    </button>
                  )}
                  <button onClick={() => run()} disabled={running} className="flex-1 rounded-md border border-[var(--hairline)] px-3 py-2 text-[12px] text-[var(--ink-dim)] disabled:opacity-50">
                    {running ? 'Trying gateway…' : 'Try gateway anyway'}
                  </button>
                </div>
              </>
            ) : (
              <>
                <button
                  onClick={() => run()}
                  disabled={running}
                  className="w-full rounded-md px-3 py-3 text-[13px] font-bold text-black disabled:opacity-50"
                  style={{ background: 'var(--octa-glow)' }}
                >
                  {running ? 'Connecting…' : steps.length ? 'Reconnect' : 'Install & Connect everything'}
                </button>
                <div className="flex gap-2">
                  {installEvt && (
                    <button onClick={installPwa} className="flex-1 rounded-md border border-[var(--hairline)] px-3 py-2 text-[12px]">
                      Add to Home Screen
                    </button>
                  )}
                  <button onClick={onClose} className="flex-1 rounded-md border border-[var(--hairline)] px-3 py-2 text-[12px] text-[var(--ink-dim)]">
                    {done ? 'Enter NEXUS' : 'Skip for now'}
                  </button>
                </div>
              </>
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
