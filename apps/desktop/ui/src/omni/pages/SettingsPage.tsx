import { useEffect, useRef, useState } from 'react';
import { enablePush, pushEnabled, pushSupported } from '@/lib/push';
import { supabaseConfigured } from '@/lib/supabase';
import { getConfig } from '@/lib/config';
import { useNavigate } from 'react-router-dom';
import { CredentialsManager } from '@/components/setup/CredentialsManager';
import { ProvidersManager } from '@/components/setup/ProvidersManager';
import { AddOnsManager } from '@/components/setup/AddOnsManager';
import { ImportKeysCard } from '@/components/setup/ImportKeysCard';
import { RepoSyncCard } from '@/components/repo/RepoSyncCard';
import {
  requestMic,
  startListening,
  speak,
  sttSupported,
  ttsSupported,
  type VoiceSession,
} from '@/lib/voice';

export default function SettingsPage() {
  const navigate = useNavigate();
  const [installEvt, setInstallEvt] = useState<any>(null);
  const [pushOn, setPushOn] = useState(false);
  const [pushMsg, setPushMsg] = useState<string>('');
  const [listening, setListening] = useState(false);
  const [heard, setHeard] = useState('');
  const voiceRef = useRef<VoiceSession | null>(null);

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

  const toggleListen = async () => {
    if (listening) {
      voiceRef.current?.stop();
      setListening(false);
      return;
    }
    const ok = await requestMic();
    if (!ok) {
      setHeard('Microphone permission denied');
      return;
    }
    setHeard('');
    voiceRef.current = startListening(
      (partial) => setHeard(partial),
      (final) => {
        setHeard(final);
        setListening(false);
      },
      (err) => {
        setHeard(err);
        setListening(false);
      },
    );
    if (voiceRef.current) setListening(true);
  };

  const museBase = getConfig().museBaseUrl;

  return (
    <div className="px-4 pb-6">
      <Section title="Connections">
        <button
          onClick={() => window.dispatchEvent(new CustomEvent('nexus:open-setup'))}
          className="mb-2 w-full rounded-md px-3 py-2 text-[12px] font-semibold text-black"
          style={{ background: 'var(--octa-glow)' }}
        >
          ⚡ Install & connect everything
        </button>
        <Row label="M.U.S.E. gateway" value={museBase || 'Not configured'} />
        <Row label="Device token" value={getConfig().museToken ? 'Paired ✓' : 'Not paired'} />
        <Row label="Supabase" value={supabaseConfigured() ? 'Connected' : 'Not configured'} />
        <Row label="Antigravity" value="Link-out (no SDK)" />
        <Row label="AI Studio" value="Link-out (no SDK)" />
      </Section>

      <Section title="MUSE repo — synced to main">
        <RepoSyncCard />
        <button
          onClick={() => navigate('/repo')}
          className="mt-2 w-full rounded-md border border-[var(--hairline)] px-3 py-2 text-[11px] font-medium text-[var(--ink)]"
        >
          Browse the full live mirror →
        </button>
      </Section>

      <Section title="AI Providers">
        <div className="mb-2">
          <ImportKeysCard />
        </div>
        <ProvidersManager />
      </Section>

      <Section title="Add-ons — CLIs · MCPs · Custom">
        <AddOnsManager />
      </Section>

      <Section title="Connections & Credentials">
        <CredentialsManager />
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
        <Row label="STT/TTS" value={sttSupported() ? 'Web Speech ready' : 'Unsupported'} />
        <div className="mt-2 flex items-center gap-2">
          <button
            onClick={toggleListen}
            disabled={!sttSupported()}
            className="rounded-md px-3 py-1.5 text-[11px] font-semibold text-black disabled:opacity-40"
            style={{ background: listening ? 'var(--state-error)' : 'var(--octa-glow)' }}
          >
            {listening ? 'Stop' : '🎤 Listen'}
          </button>
          <button
            onClick={() => speak('MUSE voice bridge online.')}
            disabled={!ttsSupported()}
            className="rounded-md border border-[var(--hairline)] px-3 py-1.5 text-[11px] disabled:opacity-40"
          >
            Test speak
          </button>
        </div>
        {heard && (
          <div className="mono mt-2 text-[11px] text-[var(--ink)]">“{heard}”</div>
        )}
        <div className="mt-1 text-[10px] text-[var(--ink-faint)]">
          Drives the existing M.U.S.E. voice bridge (Flask + Web Speech) — final
          transcripts POST to <span className="mono">/api/voice/stt</span>; not reimplemented here.
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
