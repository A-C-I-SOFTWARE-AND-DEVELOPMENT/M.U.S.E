import { useEffect, useState, useSyncExternalStore } from 'react';
import {
  fetchMirror,
  getCachedMirror,
  buildInfo,
  syncStatus,
  repoRef,
  setRepoRef,
  RepoSyncError,
  type RepoMirror,
} from '@/lib/repoSync';
import { getUpdateState, subscribeUpdate, applyUpdate, checkForUpdate } from '@/lib/appUpdate';

function relTime(iso: string): string {
  if (!iso) return '';
  const d = Date.parse(iso);
  if (Number.isNaN(d)) return '';
  const s = Math.floor((Date.now() - d) / 1000);
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

export function useAppUpdate() {
  return useSyncExternalStore(subscribeUpdate, getUpdateState, getUpdateState);
}

export function RepoSyncCard({ compact = false }: { compact?: boolean }) {
  const [mirror, setMirror] = useState<RepoMirror | null>(() => getCachedMirror());
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [slug, setSlug] = useState(() => `${repoRef().owner}/${repoRef().repo}`);
  const upd = useAppUpdate();

  const load = async (force: boolean) => {
    setLoading(true);
    setErr(null);
    try {
      setMirror(await fetchMirror(force));
    } catch (e) {
      setErr(e instanceof RepoSyncError ? e.message : 'Could not reach GitHub.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const b = buildInfo();
  const head = mirror?.head ?? null;
  const status = syncStatus(head);
  const updatable = upd.needRefresh || status === 'behind';

  const ref = repoRef();

  return (
    <div className="glass px-3 py-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span
            className="h-2.5 w-2.5 rounded-full"
            style={{
              background: updatable ? 'var(--state-warning, #FFB020)' : status === 'current' ? 'var(--state-running)' : 'var(--ink-faint)',
              boxShadow: updatable ? '0 0 8px var(--state-warning, #FFB020)' : 'none',
            }}
          />
          <div className="text-[12px] font-semibold">
            MUSE repo · <span className="mono">{ref.branch}</span>
          </div>
        </div>
        <button onClick={() => setEditing((e) => !e)} className="mono text-[9px] uppercase text-[var(--ink-faint)]">
          {ref.owner}/{ref.repo} ✎
        </button>
      </div>

      {editing && (
        <div className="mt-2 flex gap-2">
          <input
            value={slug}
            onChange={(e) => setSlug(e.target.value)}
            placeholder="owner/repo"
            className="mono flex-1 rounded-md border border-[var(--hairline)] bg-[var(--panel-solid)] px-2 py-1 text-[11px] text-[var(--ink)]"
          />
          <button
            onClick={() => {
              setRepoRef({ repoSlug: slug.trim() });
              setEditing(false);
              void load(true);
            }}
            className="rounded-md px-2.5 py-1 text-[10px] font-semibold text-black"
            style={{ background: 'var(--octa-glow)' }}
          >
            Save
          </button>
        </div>
      )}

      <div className="mt-2 space-y-1">
        <Row label="Latest on main">
          {head ? (
            <a href={head.url} target="_blank" rel="noreferrer" className="mono text-[11px] text-[var(--ink)] underline-offset-2 hover:underline">
              {head.shortSha} · {relTime(head.date)}
            </a>
          ) : (
            <span className="mono text-[11px] text-[var(--ink-faint)]">{loading ? 'syncing…' : '—'}</span>
          )}
        </Row>
        {head && !compact && <div className="truncate text-[10px] text-[var(--ink-dim)]">“{head.message}”</div>}
        <Row label="This build">
          <span className="mono text-[11px] text-[var(--ink-dim)]">{b.sha}{b.time ? ` · ${relTime(b.time)}` : ''}</span>
        </Row>
        <Row label="Status">
          <span
            className="mono text-[11px]"
            style={{ color: updatable ? 'var(--state-warning, #FFB020)' : status === 'current' ? 'var(--state-running)' : 'var(--ink-dim)' }}
          >
            {updatable ? 'update available' : status === 'current' ? 'up to date ✓' : 'synced (mirror)'}
          </span>
        </Row>
      </div>

      {err && <div className="mt-2 text-[10px] text-[var(--state-error)]">{err}</div>}

      <div className="mt-3 flex gap-2">
        <button
          onClick={() => void load(true)}
          disabled={loading}
          className="flex-1 rounded-md border border-[var(--hairline)] px-3 py-1.5 text-[11px] font-medium text-[var(--ink)] disabled:opacity-40"
        >
          {loading ? 'Syncing…' : 'Sync now'}
        </button>
        <button
          onClick={() => (updatable ? void applyUpdate() : void checkForUpdate())}
          disabled={upd.checking}
          className="flex-1 rounded-md px-3 py-1.5 text-[11px] font-semibold text-black disabled:opacity-40"
          style={{ background: updatable ? 'var(--state-warning, #FFB020)' : 'var(--octa-glow)' }}
        >
          {updatable ? '⤓ Update NEXUS' : upd.checking ? 'Checking…' : 'Check for update'}
        </button>
      </div>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-[11px] text-[var(--ink-dim)]">{label}</span>
      {children}
    </div>
  );
}
