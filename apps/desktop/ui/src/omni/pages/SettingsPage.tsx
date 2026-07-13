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
import { useUniverseStore } from '@/universe/store';
import type { FidelityPreference } from '@/universe/fidelity';

export default function SettingsPage() {
  const navigate = useNavigate();
  const [installEvt, setInstallEvt] = useState<any>(null);
  const [pushOn, setPushOn] = useState(false);
  const [pushMsg, setPushMsg] = useState<string>('');
  const [listening, setListening] = useState(false);
  const [heard, setHeard] = useState('');
  const voiceRef = useRef<VoiceSession | null>(null);
  const universeConnection = useUniverseStore((state) => state.connection);
  const universeProblem = useUniverseStore((state) => state.problem);
  const preferences = useUniverseStore((state) => state.preferences);
  const setPreferences = useUniverseStore((state) => state.setPreferences);
  const diagnostics = useUniverseStore((state) => state.diagnostics);

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
          Install & connect everything
        </button>
        <Row label="M.U.S.E. gateway" value={museBase || 'Not configured'} />
        <Row label="Device token" value={getConfig().museToken ? 'Pairing credential stored' : 'Not paired'} />
        <Row label="Atlas universe" value={universeConnection} />
        {universeProblem && <div className="universe-error-copy mt-2">{universeProblem.message}{universeProblem.correlationId ? ` · ${universeProblem.correlationId}` : ''}</div>}
        <Row label="Supabase" value={supabaseConfigured() ? 'Configured · reachability not probed' : 'Not configured'} />
        <Row label="Antigravity" value="Link-out (no SDK)" />
        <Row label="AI Studio" value="Link-out (no SDK)" />
      </Section>

      <Section title="Atlas rendering & comfort">
        <div className="settings-control-grid">
          <label>Fidelity tier<select value={preferences.fidelity} onChange={(event) => setPreferences({ fidelity: event.target.value as FidelityPreference })}><option value="auto">Automatic</option><option value="cinema">Cinema</option><option value="ultra">Ultra</option><option value="high">High</option><option value="balanced">Balanced</option><option value="accessible-2d">Accessible 2D</option></select></label>
          <label>Depth strength <output>{Math.round(preferences.depthStrength * 100)}%</output><input type="range" min={0} max={1} step={0.05} value={preferences.depthStrength} onChange={(event) => setPreferences({ depthStrength: Number(event.target.value) })} /></label>
          <label>Particle density <output>{Math.round(preferences.particleDensity * 100)}%</output><input type="range" min={0} max={1} step={0.05} value={preferences.particleDensity} onChange={(event) => setPreferences({ particleDensity: Number(event.target.value) })} /></label>
          <label>Comfort vignette <output>{Math.round(preferences.comfortVignette * 100)}%</output><input type="range" min={0} max={1} step={0.05} value={preferences.comfortVignette} onChange={(event) => setPreferences({ comfortVignette: Number(event.target.value) })} /></label>
          <label>Text scale <output>{Math.round(preferences.textScale * 100)}%</output><input type="range" min={0.9} max={1.35} step={0.05} value={preferences.textScale} onChange={(event) => setPreferences({ textScale: Number(event.target.value) })} /></label>
        </div>
        <div className="settings-toggle-grid">
          <label><input type="checkbox" checked={preferences.reducedMotion} onChange={(event) => setPreferences({ reducedMotion: event.target.checked })} /> Reduced motion</label>
          <label><input type="checkbox" checked={preferences.twoDOnly} onChange={(event) => setPreferences({ twoDOnly: event.target.checked })} /> 2D-only controls</label>
          <label><input type="checkbox" checked={preferences.captions} onChange={(event) => setPreferences({ captions: event.target.checked })} /> Captions and text cues</label>
          <label><input type="checkbox" checked={preferences.colorSafe} onChange={(event) => setPreferences({ colorSafe: event.target.checked })} /> Color-safe status palette</label>
        </div>
      </Section>

      <Section title="Atlas diagnostics">
        <div role="status" aria-live="polite" className="sr-only">Rendering tier {diagnostics.tier}</div>
        <div className="diagnostics-grid">
          <Row label="Tier" value={diagnostics.tier} />
          <Row label="Device pixel ratio" value={diagnostics.dpr == null ? 'Not measured' : String(diagnostics.dpr)} />
          <Row label="Frame time average" value={diagnostics.frameTimeMs == null ? 'Not measured' : `${diagnostics.frameTimeMs} ms`} />
          <Row label="Draw calls" value={diagnostics.drawCalls == null ? 'Not measured' : diagnostics.drawCalls.toLocaleString()} />
          <Row label="Triangles" value={diagnostics.triangles == null ? 'Not measured' : diagnostics.triangles.toLocaleString()} />
          <Row label="Texture memory estimate" value={diagnostics.textureMemoryMb == null ? 'Not measured' : `~${diagnostics.textureMemoryMb} MB`} />
          <Row label="Graph nodes" value={diagnostics.graphNodeCount == null ? 'Not measured' : diagnostics.graphNodeCount.toLocaleString()} />
          <Row label="Last event cursor" value={String(diagnostics.lastEventCursor)} />
        </div>
        <div className="mono mt-2 text-[10px] text-[var(--ink-faint)]">Degraded reasons: {diagnostics.degradedReasons.join(', ') || 'None reported'}</div>
      </Section>

      <Section title="MUSE repo — synced to main">
        <RepoSyncCard />
        <button
          onClick={() => navigate('/repo')}
          className="mt-2 w-full rounded-md border border-[var(--hairline)] px-3 py-2 text-[11px] font-medium text-[var(--ink)]"
        >
          Browse the repository mirror →
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
            {listening ? 'Stop capture' : 'Start voice capture'}
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
        MUSE ATLAS · Unified Agent Command Console · v0.1.0
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
