// ============================================================================
// SignInPage — honest sign-in surface.
//
//   • Supabase configured → real email/password form + OAuth buttons (Google,
//     GitHub). Sessions are minted by GoTrue and re-verified server-side.
//   • Supabase unset       → NO fake login. We clearly say sign-in is
//     unavailable and label the session "anonymous — not signed in".
//
// There is no demo account, no mock user, no "continue as guest that looks
// signed in". Anonymous-local is shown as exactly that.
// ============================================================================

import { useEffect, useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth, type OAuthProvider } from '@/auth/AuthProvider';

export default function SignInPage() {
  const navigate = useNavigate();
  const auth = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [mode, setMode] = useState<'signin' | 'signup'>('signin');
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  // When an OAuth redirect lands back here with tokens in the URL fragment,
  // nudge the provider to adopt the session.
  useEffect(() => {
    if (window.location.hash.includes('access_token')) {
      window.dispatchEvent(new CustomEvent('nexus:auth-callback'));
    }
  }, []);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setNotice(null);
    const res =
      mode === 'signin'
        ? await auth.signInWithPassword(email, password)
        : await auth.signUpWithPassword(email, password);
    setBusy(false);
    if (res.ok) {
      if (mode === 'signup' && !auth.signedIn) {
        setNotice('Account created. Check your email to confirm, then sign in.');
      }
    }
  };

  const oauth = (provider: OAuthProvider) => {
    setNotice(null);
    const res = auth.signInWithOAuth(provider);
    if (!res.ok && res.error) setNotice(res.error);
  };

  // ---- Signed in: confirmation + sign-out ----------------------------------
  if (auth.signedIn && auth.user) {
    return (
      <Shell>
        <div className="hud-label mb-2">Signed in</div>
        <div className="glass px-4 py-4">
          <div className="text-[13px] text-[var(--ink)]">
            {auth.user.email ?? 'Verified account'}
          </div>
          <div className="mono mt-1 text-[10px] text-[var(--ink-faint)]">
            session verified · supabase
          </div>
          <div className="mt-4 flex gap-2">
            <button
              onClick={() => navigate('/')}
              className="flex-1 rounded-md px-3 py-2 text-[12px] font-semibold text-black"
              style={{ background: 'var(--octa-glow)' }}
            >
              Continue
            </button>
            <button
              onClick={() => void auth.signOut()}
              className="rounded-md border border-[var(--hairline)] px-3 py-2 text-[12px] text-[var(--ink)]"
            >
              Sign out
            </button>
          </div>
        </div>
      </Shell>
    );
  }

  // ---- Supabase unset: honest anonymous-local state ------------------------
  if (!auth.configured) {
    return (
      <Shell>
        <div className="hud-label mb-2">Sign in</div>
        <div className="glass px-4 py-4">
          <div
            className="mb-3 rounded-md px-3 py-2 text-[11px]"
            style={{
              border: '1px solid var(--hairline)',
              color: 'var(--ink-dim)',
              background: 'rgba(255,255,255,0.02)',
            }}
          >
            <span className="mono">anonymous — not signed in</span>
          </div>
          <p className="text-[12px] leading-relaxed text-[var(--ink-dim)]">
            Sign-in is unavailable because no Supabase project is configured. NEXUS
            is running in <span className="mono">anonymous-local</span> mode — your
            data stays on this device and no account is attached.
          </p>
          <p className="mt-3 text-[11px] leading-relaxed text-[var(--ink-faint)]">
            To enable real accounts, set <span className="mono">VITE_SUPABASE_URL</span>{' '}
            and <span className="mono">VITE_SUPABASE_ANON_KEY</span>, then verify
            tokens server-side with <span className="mono">SUPABASE_JWT_SECRET</span>.
          </p>
          <button
            onClick={() => navigate('/')}
            className="mt-4 w-full rounded-md border border-[var(--hairline)] px-3 py-2 text-[12px] text-[var(--ink)]"
          >
            Continue anonymously →
          </button>
        </div>
      </Shell>
    );
  }

  // ---- Supabase configured: real email + OAuth ------------------------------
  return (
    <Shell>
      <div className="hud-label mb-2">{mode === 'signin' ? 'Sign in' : 'Create account'}</div>
      <div className="glass px-4 py-4">
        {auth.loading && (
          <div className="mb-3 text-[11px] text-[var(--ink-faint)]">Checking session…</div>
        )}

        <div className="grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={() => oauth('google')}
            disabled={busy}
            className="rounded-md border border-[var(--hairline)] px-3 py-2 text-[12px] font-medium text-[var(--ink)] disabled:opacity-40"
          >
            Continue with Google
          </button>
          <button
            type="button"
            onClick={() => oauth('github')}
            disabled={busy}
            className="rounded-md border border-[var(--hairline)] px-3 py-2 text-[12px] font-medium text-[var(--ink)] disabled:opacity-40"
          >
            Continue with GitHub
          </button>
        </div>

        <div className="my-3 flex items-center gap-2 text-[10px] text-[var(--ink-faint)]">
          <span className="h-px flex-1" style={{ background: 'var(--hairline)' }} />
          or use email
          <span className="h-px flex-1" style={{ background: 'var(--hairline)' }} />
        </div>

        <form onSubmit={submit} className="flex flex-col gap-2">
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            autoComplete="email"
            className="rounded-md border border-[var(--hairline)] bg-transparent px-3 py-2 text-[13px] text-[var(--ink)] outline-none"
          />
          <input
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Password"
            autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
            className="rounded-md border border-[var(--hairline)] bg-transparent px-3 py-2 text-[13px] text-[var(--ink)] outline-none"
          />
          <button
            type="submit"
            disabled={busy}
            className="mt-1 rounded-md px-3 py-2 text-[12px] font-semibold text-black disabled:opacity-40"
            style={{ background: 'var(--octa-glow)' }}
          >
            {busy ? 'Working…' : mode === 'signin' ? 'Sign in' : 'Create account'}
          </button>
        </form>

        {auth.error && (
          <div className="mt-2 text-[11px]" style={{ color: 'var(--state-error)' }}>
            {auth.error}
          </div>
        )}
        {notice && (
          <div className="mt-2 text-[11px] text-[var(--ink-dim)]">{notice}</div>
        )}

        <button
          type="button"
          onClick={() => {
            setNotice(null);
            setMode((m) => (m === 'signin' ? 'signup' : 'signin'));
          }}
          className="mt-3 w-full text-center text-[11px] text-[var(--ink-faint)] underline"
        >
          {mode === 'signin' ? 'Need an account? Sign up' : 'Have an account? Sign in'}
        </button>
      </div>
    </Shell>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="mx-auto w-full max-w-sm px-4 pb-6 pt-6">
      <div className="mono mb-4 text-center text-[10px] tracking-widest text-[var(--ink-faint)]">
        NEXUS
      </div>
      {children}
    </div>
  );
}
