import { useEffect, useState } from 'react';
import { enablePush, pushEnabled, pushSupported } from '@/lib/push';

export default function SettingsPage() {
  const [installEvt, setInstallEvt] = useState<any>(null);
  const [pushOn, setPushOn] = useState(false);
  const [pushMsg, setPushMsg] = useState<string>('');

  useEffect(() => {
    const handler = (e: Event) => {
      e.preventDefault();
      setInstallEvt(e);
    };
    window.addEventListener('beforeinstallprompt', handler);
    pushEnabled().then(setPushOn);
    return () => window.removeEventListener('beforeinstallprompt', handler);
  }, []);

  const install = async () => {
    if (!installEvt) return;
    installEvt.prompt();
    await installEvt.userChoice;
    setInstallEvt(null);
  };

  const togglePush = async () => {
    const res = await enablePush();
    setPushOn(res.ok);
    setPushMsg(res.ok ? 'Notifications enabled' : res.reason ?? 'Failed');
  };

  const museBase = import.meta.env.VITE_MUSE_BASE_URL ?? '';

  return (
    <div className="px-4 pb-6">
      <Section title="Connections">
        <Row label="M.U.S.E. base URL" value={museBase || 'Not configured'} />
        <Row label="Antigravity" value="Link-out (no SDK)" />
        <Row label="AI Studio" value="Link-out (no SDK)" />
      </Section>

      <Section title="Install">
        <button
          onClick={install}
          disabled={!installEvt}
          className="w-full rounded-md px-3 py-2 text-[12px] font-semibold text-black disabled:opacity-40"
          style={{ background: 'var(--octa-glow)' }}
        >
          {installEvt ? 'Add NEXUS to home screen' : 'Already installed / not available'}
        </button>
      </Section>

      <Section title="Notifications">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-[12px]">Push notifications</div>
            <div className="text-[10px] text-[var(--ink-faint)]">
              Completions, errors, owner-gated approvals
            </div>
          </div>
          <button
            onClick={togglePush}
            className="rounded-full px-3 py-1 text-[11px] font-medium"
            style={{
              background: pushOn ? 'var(--octa-glow)' : 'transparent',
              border: '1px solid var(--hairline)',
              color: pushOn ? '#000' : 'var(--ink)',
            }}
          >
            {pushOn ? 'On' : pushSupported() ? 'Enable' : 'Unsupported'}
          </button>
        </div>
        {pushMsg && <div className="mt-1 text-[10px] text-[var(--ink-dim)]">{pushMsg}</div>}
      </Section>

      <Section title="Companion daemon">
        <Row label="Pairing" value="Open NEXUS daemon app → scan code" />
        <div className="mt-1 text-[10px] leading-snug text-[var(--ink-faint)]">
          The Android daemon (companion-android) holds an always-on connection to
          M.U.S.E. for background status + authorization relays. It shares this
          backend contract and auth.
        </div>
      </Section>

      <Section title="Voice bridge">
        <Row label="STT/TTS" value="M.U.S.E. Flask + Web Speech" />
        <div className="mt-1 text-[10px] text-[var(--ink-faint)]">
          Uses the existing M.U.S.E. voice bridge — not reimplemented here.
        </div>
      </Section>

      <div className="mono mt-6 text-center text-[9px] text-[var(--ink-faint)]">
        NEXUS · Unified Agent Command Console · v0.1.0
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-3">
      <div className="hud-label mb-2 mt-1">{title}</div>
      <div className="glass px-3 py-3">{children}</div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 py-1">
      <span className="text-[12px] text-[var(--ink-dim)]">{label}</span>
      <span className="mono truncate text-[11px] text-[var(--ink)]">{value}</span>
    </div>
  );
}
