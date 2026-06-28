// ============================================================================
// AuthProvider — the single source of truth for "who is signed in".
//
// Two HONEST modes, never blurred:
//
//   • mode: 'supabase'        — VITE_SUPABASE_URL (+ anon key) is set. Real
//     email/password + OAuth sessions go through the Supabase GoTrue REST API
//     (no SDK dependency; mirrors src/lib/supabase.ts's import-free style). A
//     valid access token + a /auth/v1/user echo are required before we ever
//     report signedIn:true.
//
//   • mode: 'anonymous-local' — Supabase is unset. We expose an EXPLICIT
//     { signedIn:false, mode:'anonymous-local' } state. The UI MUST label this
//     "anonymous — not signed in". We NEVER fabricate an authenticated user;
//     there is no demo/mock account.
//
// The browser only ever holds the public anon key + the user's own access
// token. The JWT signing secret lives server-side (SUPABASE_JWT_SECRET) and is
// the real security boundary — see api/auth/session.ts. A client-asserted user
// id is never trusted by the server.
// ============================================================================

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { supabaseConfigured } from '@/lib/supabase';
import { supabaseUrlCfg, supabaseAnonCfg } from '@/lib/config';

export type AuthMode = 'supabase' | 'anonymous-local';

export interface AuthUser {
  id: string;
  email: string | null;
}

/** OAuth providers we surface buttons for. Add-only; honest about what's wired. */
export type OAuthProvider = 'google' | 'github';

export interface AuthState {
  /** True ONLY when a real, server-verifiable session exists. */
  signedIn: boolean;
  /** Which world we're in. 'anonymous-local' is never faked as authenticated. */
  mode: AuthMode;
  /** Whether a Supabase project is configured at all. */
  configured: boolean;
  /** The signed-in user, or null. Never a placeholder. */
  user: AuthUser | null;
  /** The user's own access token (browser-held; server re-verifies it). */
  accessToken: string | null;
  /** Initial session probe still in flight. */
  loading: boolean;
  /** Last auth error surfaced to the UI (honest, not swallowed). */
  error: string | null;
}

export interface AuthContextValue extends AuthState {
  signInWithPassword(email: string, password: string): Promise<{ ok: boolean; error?: string }>;
  signUpWithPassword(email: string, password: string): Promise<{ ok: boolean; error?: string }>;
  signInWithOAuth(provider: OAuthProvider): { ok: boolean; error?: string };
  signOut(): Promise<void>;
}

// ---- Token persistence (the user's OWN token only; never a secret) ----------
const TOKEN_KEY = 'nexus.auth.session.v1';

interface StoredSession {
  access_token: string;
  refresh_token: string;
  expires_at: number; // epoch seconds
}

function loadSession(): StoredSession | null {
  if (typeof localStorage === 'undefined') return null;
  try {
    const raw = localStorage.getItem(TOKEN_KEY);
    if (!raw) return null;
    const s = JSON.parse(raw) as Partial<StoredSession>;
    if (!s.access_token) return null;
    return {
      access_token: s.access_token,
      refresh_token: s.refresh_token ?? '',
      expires_at: typeof s.expires_at === 'number' ? s.expires_at : 0,
    };
  } catch {
    return null;
  }
}

function saveSession(s: StoredSession | null): void {
  if (typeof localStorage === 'undefined') return;
  try {
    if (s) localStorage.setItem(TOKEN_KEY, JSON.stringify(s));
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* ignore */
  }
}

// ---- GoTrue REST helpers (no @supabase/supabase-js dependency) --------------
function authBase(): string {
  return `${supabaseUrlCfg()}/auth/v1`;
}

function anonHeaders(extra: Record<string, string> = {}): Record<string, string> {
  return {
    apikey: supabaseAnonCfg(),
    'Content-Type': 'application/json',
    ...extra,
  };
}

interface TokenResponse {
  access_token?: string;
  refresh_token?: string;
  expires_in?: number;
  user?: { id?: string; email?: string | null };
  error?: string;
  error_description?: string;
  msg?: string;
}

function toSession(t: TokenResponse): StoredSession | null {
  if (!t.access_token) return null;
  const ttl = typeof t.expires_in === 'number' ? t.expires_in : 3600;
  return {
    access_token: t.access_token,
    refresh_token: t.refresh_token ?? '',
    expires_at: Math.floor(Date.now() / 1000) + ttl,
  };
}

function errText(t: TokenResponse, fallback: string): string {
  return t.error_description || t.msg || t.error || fallback;
}

/** Fetch the verified user for an access token (anon-key + bearer). null if invalid. */
async function fetchUser(accessToken: string): Promise<AuthUser | null> {
  try {
    const res = await fetch(`${authBase()}/user`, {
      headers: anonHeaders({ Authorization: `Bearer ${accessToken}` }),
    });
    if (!res.ok) return null;
    const u = (await res.json()) as { id?: string; email?: string | null };
    return u?.id ? { id: u.id, email: u.email ?? null } : null;
  } catch {
    return null;
  }
}

async function refreshSession(refreshToken: string): Promise<StoredSession | null> {
  if (!refreshToken) return null;
  try {
    const res = await fetch(`${authBase()}/token?grant_type=refresh_token`, {
      method: 'POST',
      headers: anonHeaders(),
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!res.ok) return null;
    return toSession((await res.json()) as TokenResponse);
  } catch {
    return null;
  }
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const configured = supabaseConfigured();
  const mode: AuthMode = configured ? 'supabase' : 'anonymous-local';

  const [user, setUser] = useState<AuthUser | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  // No Supabase ⇒ nothing to probe; we're immediately in the explicit
  // anonymous-local state (loading resolves false right away).
  const [loading, setLoading] = useState<boolean>(configured);
  const [error, setError] = useState<string | null>(null);

  const applySession = useCallback((s: StoredSession | null, u: AuthUser | null) => {
    saveSession(s);
    setAccessToken(s?.access_token ?? null);
    setUser(u);
  }, []);

  // Initial probe: rehydrate a stored session, refresh if near expiry, and
  // confirm it against /auth/v1/user. Anything unverifiable is dropped — we
  // never report a session we can't stand behind.
  useEffect(() => {
    if (!configured) {
      setLoading(false);
      return;
    }
    let alive = true;
    (async () => {
      let session = loadSession();
      if (session && session.expires_at - 60 <= Math.floor(Date.now() / 1000)) {
        session = (await refreshSession(session.refresh_token)) ?? null;
      }
      const verified = session ? await fetchUser(session.access_token) : null;
      if (!alive) return;
      if (session && verified) applySession(session, verified);
      else applySession(null, null);
      setLoading(false);
    })();
    return () => {
      alive = false;
    };
  }, [configured, applySession]);

  const signInWithPassword = useCallback(
    async (email: string, password: string) => {
      if (!configured) {
        return { ok: false, error: 'Supabase is not configured — sign-in is unavailable.' };
      }
      setError(null);
      try {
        const res = await fetch(`${authBase()}/token?grant_type=password`, {
          method: 'POST',
          headers: anonHeaders(),
          body: JSON.stringify({ email, password }),
        });
        const body = (await res.json()) as TokenResponse;
        if (!res.ok) {
          const msg = errText(body, 'Sign-in failed');
          setError(msg);
          return { ok: false, error: msg };
        }
        const session = toSession(body);
        const verified = session ? await fetchUser(session.access_token) : null;
        if (!session || !verified) {
          const msg = 'Sign-in failed — no valid session returned.';
          setError(msg);
          return { ok: false, error: msg };
        }
        applySession(session, verified);
        return { ok: true };
      } catch (e) {
        const msg = `Sign-in error: ${(e as Error).message}`;
        setError(msg);
        return { ok: false, error: msg };
      }
    },
    [configured, applySession],
  );

  const signUpWithPassword = useCallback(
    async (email: string, password: string) => {
      if (!configured) {
        return { ok: false, error: 'Supabase is not configured — sign-up is unavailable.' };
      }
      setError(null);
      try {
        const res = await fetch(`${authBase()}/signup`, {
          method: 'POST',
          headers: anonHeaders(),
          body: JSON.stringify({ email, password }),
        });
        const body = (await res.json()) as TokenResponse;
        if (!res.ok) {
          const msg = errText(body, 'Sign-up failed');
          setError(msg);
          return { ok: false, error: msg };
        }
        // With email confirmation enabled, no access_token is returned yet —
        // that's an honest "check your inbox" outcome, not a session.
        const session = toSession(body);
        if (session) {
          const verified = await fetchUser(session.access_token);
          if (verified) applySession(session, verified);
        }
        return { ok: true };
      } catch (e) {
        const msg = `Sign-up error: ${(e as Error).message}`;
        setError(msg);
        return { ok: false, error: msg };
      }
    },
    [configured, applySession],
  );

  // OAuth is a full-page redirect to GoTrue's /authorize, which bounces back to
  // our /api/auth/callback edge handler and then to /signin with tokens in the
  // URL fragment. We only build + navigate to the URL here.
  const signInWithOAuth = useCallback(
    (provider: OAuthProvider) => {
      if (!configured) {
        return { ok: false, error: 'Supabase is not configured — OAuth is unavailable.' };
      }
      if (typeof window === 'undefined') {
        return { ok: false, error: 'OAuth requires a browser.' };
      }
      const redirectTo = `${window.location.origin}/api/auth/callback`;
      const url =
        `${authBase()}/authorize?provider=${encodeURIComponent(provider)}` +
        `&redirect_to=${encodeURIComponent(redirectTo)}`;
      window.location.assign(url);
      return { ok: true };
    },
    [configured],
  );

  const signOut = useCallback(async () => {
    const token = accessToken;
    applySession(null, null);
    setError(null);
    if (configured && token) {
      try {
        await fetch(`${authBase()}/logout`, {
          method: 'POST',
          headers: anonHeaders({ Authorization: `Bearer ${token}` }),
        });
      } catch {
        /* best-effort; local session already cleared */
      }
    }
  }, [configured, accessToken, applySession]);

  // Adopt a session handed back by the OAuth callback via the URL fragment
  // (#access_token=...&refresh_token=...). SignInPage triggers this event.
  useEffect(() => {
    if (!configured) return;
    const adopt = async () => {
      const hash = window.location.hash.startsWith('#')
        ? window.location.hash.slice(1)
        : window.location.hash;
      const params = new URLSearchParams(hash);
      const access = params.get('access_token');
      if (!access) return;
      const refresh = params.get('refresh_token') ?? '';
      const expiresIn = Number(params.get('expires_in') ?? '3600');
      const session: StoredSession = {
        access_token: access,
        refresh_token: refresh,
        expires_at: Math.floor(Date.now() / 1000) + (Number.isFinite(expiresIn) ? expiresIn : 3600),
      };
      const verified = await fetchUser(access);
      if (verified) {
        applySession(session, verified);
        // Strip the tokens out of the address bar.
        history.replaceState(null, '', window.location.pathname + window.location.search);
      }
    };
    void adopt();
    window.addEventListener('nexus:auth-callback', adopt);
    return () => window.removeEventListener('nexus:auth-callback', adopt);
  }, [configured, applySession]);

  const value = useMemo<AuthContextValue>(
    () => ({
      signedIn: !!user,
      mode,
      configured,
      user,
      accessToken,
      loading,
      error,
      signInWithPassword,
      signUpWithPassword,
      signInWithOAuth,
      signOut,
    }),
    [
      user,
      mode,
      configured,
      accessToken,
      loading,
      error,
      signInWithPassword,
      signUpWithPassword,
      signInWithOAuth,
      signOut,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

/** Access the auth context. Throws if used outside <AuthProvider>. */
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within <AuthProvider>');
  return ctx;
}
