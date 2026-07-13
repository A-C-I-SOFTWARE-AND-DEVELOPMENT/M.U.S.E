import { useEffect, useMemo, useState } from 'react';
import { fetchPulls, RepoSyncError, type PullRequest } from '@/lib/repoSync';

type Filter = 'all' | 'merged' | 'open' | 'closed';

function relTime(iso?: string): string {
  if (!iso) return '';
  const d = Date.parse(iso);
  if (Number.isNaN(d)) return '';
  const s = Math.floor((Date.now() - d) / 1000);
  if (s < 3600) return `${Math.max(1, Math.floor(s / 60))}m`;
  if (s < 86400) return `${Math.floor(s / 3600)}h`;
  if (s < 86400 * 30) return `${Math.floor(s / 86400)}d`;
  return `${Math.floor(s / (86400 * 30))}mo`;
}

function badge(p: PullRequest): { label: string; color: string } {
  if (p.merged) return { label: 'merged', color: 'var(--acc-creativity, #C264FE)' };
  if (p.state === 'open') return { label: 'open', color: 'var(--state-running)' };
  return { label: 'closed', color: 'var(--state-error)' };
}

export function PullList() {
  const [pulls, setPulls] = useState<PullRequest[]>([]);
  const [page, setPage] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [q, setQ] = useState('');
  const [filter, setFilter] = useState<Filter>('all');

  const loadPage = async (next: number) => {
    setLoading(true);
    setErr(null);
    try {
      const res = await fetchPulls(next, 50);
      setPulls((prev) => (next === 1 ? res.pulls : [...prev, ...res.pulls]));
      setHasMore(res.hasMore);
      setPage(next);
    } catch (e) {
      setErr(e instanceof RepoSyncError ? e.message : 'Could not load pull requests.');
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    void loadPage(1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const s = q.trim().toLowerCase();
  const filtered = useMemo(
    () =>
      pulls.filter((p) => {
        if (filter === 'merged' && !p.merged) return false;
        if (filter === 'open' && p.state !== 'open') return false;
        if (filter === 'closed' && (p.state !== 'closed' || p.merged)) return false;
        if (s && !(`#${p.number} ${p.title} ${p.user}`.toLowerCase().includes(s))) return false;
        return true;
      }),
    [pulls, filter, s],
  );

  const mergedCount = pulls.filter((p) => p.merged).length;
  const lo = pulls.length ? pulls[0].number : 0;
  const hi = pulls.length ? pulls[pulls.length - 1].number : 0;

  return (
    <div>
      <div className="mono mb-2 text-[10px] text-[var(--ink-dim)]">
        {pulls.length ? `#${lo} → #${hi} · ${pulls.length} loaded · ${mergedCount} merged to main` : loading ? 'loading pull requests…' : '—'}
      </div>

      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Search pull requests…"
        className="mb-2 w-full rounded-md border border-[var(--hairline)] bg-[var(--panel-solid)] px-3 py-2 text-[12px] text-[var(--ink)]"
      />
      <div className="mb-2 flex flex-wrap gap-1.5">
        {(['all', 'merged', 'open', 'closed'] as Filter[]).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className="rounded-full border px-2.5 py-0.5 text-[10px]"
            style={{ borderColor: filter === f ? 'var(--octa-glow)' : 'var(--hairline)', color: filter === f ? 'var(--octa-glow)' : 'var(--ink-dim)' }}
          >
            {f}
          </button>
        ))}
      </div>

      {err && <div className="glass mb-2 px-3 py-2 text-[11px] text-[var(--state-error)]">{err}</div>}

      <div className="flex flex-col gap-1">
        {filtered.map((p) => {
          const b = badge(p);
          return (
            <a key={p.number} href={p.url} target="_blank" rel="noreferrer" className="glass flex items-center justify-between px-3 py-2 active:scale-[0.99]">
              <div className="min-w-0">
                <div className="truncate text-[12px] text-[var(--ink)]">
                  <span className="mono text-[var(--ink-faint)]">#{p.number}</span> {p.title}
                </div>
                <div className="mono text-[9px] text-[var(--ink-faint)]">
                  {p.user} · {p.merged && p.mergedAt ? `merged ${relTime(p.mergedAt)} ago → ${p.baseRef}` : `opened ${relTime(p.createdAt)} ago`}
                </div>
              </div>
              <span className="mono shrink-0 rounded-full px-1.5 py-0.5 text-[8px]" style={{ color: b.color, border: `1px solid ${b.color}55` }}>
                {b.label}
              </span>
            </a>
          );
        })}
        {!loading && filtered.length === 0 && <div className="py-6 text-center text-[11px] text-[var(--ink-dim)]">No pull requests match.</div>}
      </div>

      {hasMore && (
        <button
          onClick={() => void loadPage(page + 1)}
          disabled={loading}
          className="mt-2 w-full rounded-md border border-[var(--hairline)] px-3 py-2 text-[11px] font-medium text-[var(--ink)] disabled:opacity-40"
        >
          {loading ? 'Loading…' : 'Load older pull requests'}
        </button>
      )}
    </div>
  );
}
