import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  fetchMirror,
  getCachedMirror,
  mirrorCounts,
  RepoSyncError,
  type RepoMirror,
  type RepoItem,
  type McpServer,
} from '@/lib/repoSync';
import { RepoSyncCard } from '@/components/repo/RepoSyncCard';
import { FileBrowser } from '@/components/repo/FileBrowser';
import { PullList } from '@/components/repo/PullList';

type SectionKey = 'plugins' | 'providers' | 'skills' | 'mcpServers' | 'optionalMcps' | 'docs';
type Mode = 'inventory' | 'files' | 'pulls';

const TRANSPORT_COLOR: Record<string, string> = {
  http: 'var(--state-running)',
  sse: 'var(--acc-reasoning, #7C9EFF)',
  stdio: 'var(--acc-creativity, #C264FE)',
};

export default function RepoPage() {
  const navigate = useNavigate();
  const [mirror, setMirror] = useState<RepoMirror | null>(() => getCachedMirror());
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [section, setSection] = useState<SectionKey>('plugins');
  const [mode, setMode] = useState<Mode>('inventory');
  const [q, setQ] = useState('');

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

  const counts = mirror ? mirrorCounts(mirror) : [];
  const items: RepoItem[] = useMemo(() => {
    if (!mirror) return [];
    if (section === 'mcpServers') return [];
    return mirror[section];
  }, [mirror, section]);

  const s = q.trim().toLowerCase();
  const filteredItems = useMemo(
    () => items.filter((i) => !s || i.name.toLowerCase().includes(s) || (i.category ?? '').toLowerCase().includes(s)),
    [items, s],
  );
  const filteredMcp: McpServer[] = useMemo(() => {
    if (!mirror || section !== 'mcpServers') return [];
    return mirror.mcpServers.filter((m) => !s || m.name.toLowerCase().includes(s));
  }, [mirror, section, s]);

  return (
    <div className="px-4 pb-6">
      <div className="hud-label mb-2 mt-1">Repo Mirror — synced to GitHub main</div>
      <p className="mb-3 text-[11px] leading-relaxed text-[var(--ink-dim)]">
        The entire MUSE repository, end-to-end — browse <b className="text-[var(--ink)]">every file</b>, the full
        <b className="text-[var(--ink)]"> pull-request history</b> (#1 → latest, every merge to main), and the parsed
        inventory (plugins · providers · skills · MCPs · docs) — read straight from <b className="text-[var(--ink)]">main</b> on
        GitHub. One-click update pulls the newest build.
      </p>

      <div className="mb-3">
        <RepoSyncCard />
      </div>

      {/* Mode: Inventory · Files · Pull requests */}
      <div className="mb-3 grid grid-cols-3 gap-1 rounded-lg border border-[var(--hairline)] p-1">
        {([
          ['inventory', 'Inventory'],
          ['files', 'Files'],
          ['pulls', 'Pull requests'],
        ] as [Mode, string][]).map(([m, label]) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            className="rounded-md py-1.5 text-[11px] font-medium"
            style={{ background: mode === m ? 'var(--octa-glow)' : 'transparent', color: mode === m ? '#000' : 'var(--ink-dim)' }}
          >
            {label}
          </button>
        ))}
      </div>

      {mode === 'files' && <FileBrowser />}
      {mode === 'pulls' && <PullList />}

      {mode === 'inventory' && (
        <>
      {/* Count chips → section selector */}
      <div className="mb-2 grid grid-cols-3 gap-1.5">
        {counts.map((c) => (
          <button
            key={c.key}
            onClick={() => { setSection(c.key as SectionKey); setQ(''); }}
            className="glass flex flex-col items-start px-2.5 py-2 text-left"
            style={{ borderColor: section === c.key ? 'var(--octa-glow)' : undefined }}
          >
            <span className="mono text-[15px] font-semibold" style={{ color: section === c.key ? 'var(--octa-glow)' : 'var(--ink)' }}>{c.n}</span>
            <span className="text-[9px] text-[var(--ink-dim)]">{c.label}</span>
          </button>
        ))}
      </div>

      {err && (
        <div className="glass mb-2 px-3 py-3 text-center">
          <div className="text-[11px] text-[var(--state-error)]">{err}</div>
          {!mirror && <div className="mt-1 text-[10px] text-[var(--ink-faint)]">Showing nothing until GitHub is reachable. Add a GITHUB_TOKEN in Settings to lift the anon rate limit.</div>}
        </div>
      )}

      {mirror?.truncated && (
        <div className="mb-2 text-[10px] text-[var(--state-warning,#FFB020)]">Repo tree is large — list is partial. Counts reflect what GitHub returned.</div>
      )}

      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder={`Search ${section === 'mcpServers' ? 'MCP servers' : section}…`}
        className="mb-2 w-full rounded-md border border-[var(--hairline)] bg-[var(--panel-solid)] px-3 py-2 text-[12px] text-[var(--ink)]"
      />

      {loading && !mirror ? (
        <div className="py-6 text-center text-[12px] text-[var(--ink-dim)]">Mirroring main…</div>
      ) : section === 'mcpServers' ? (
        <div className="flex flex-col gap-1.5">
          {filteredMcp.map((m) => (
            <div key={m.name} className="glass flex items-center justify-between px-3 py-2">
              <div className="min-w-0">
                <div className="mono truncate text-[12px] text-[var(--ink)]">{m.name}{m.optional ? ' ·' : ''}<span className="text-[var(--ink-faint)]">{m.optional ? ' optional' : ''}</span></div>
                <div className="mono truncate text-[9px] text-[var(--ink-faint)]">{m.url || m.command || '—'}</div>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <span className="mono rounded-full px-1.5 py-0.5 text-[8px]" style={{ color: TRANSPORT_COLOR[m.transport], border: `1px solid ${TRANSPORT_COLOR[m.transport]}55` }}>{m.transport}</span>
                <button onClick={() => navigate('/settings')} className="mono text-[10px]" style={{ color: 'var(--octa-glow)' }}>configure</button>
              </div>
            </div>
          ))}
          {filteredMcp.length === 0 && <div className="py-6 text-center text-[11px] text-[var(--ink-dim)]">{mirror ? 'No MCP servers match.' : 'Sync to load .mcp.json.'}</div>}
        </div>
      ) : (
        <div className="flex flex-col gap-1.5">
          {filteredItems.map((i) => (
            <a
              key={i.id}
              href={i.url}
              target="_blank"
              rel="noreferrer"
              className="glass flex items-center justify-between px-3 py-2 active:scale-[0.99]"
            >
              <div className="min-w-0">
                <div className="mono truncate text-[12px] text-[var(--ink)]">{i.name}</div>
                {i.category && <div className="mono text-[9px] text-[var(--ink-faint)]">{i.category}{i.optional ? ' · optional' : ''}</div>}
              </div>
              <span className="mono shrink-0 text-[10px] text-[var(--ink-faint)]">source ↗</span>
            </a>
          ))}
          {filteredItems.length === 0 && <div className="py-6 text-center text-[11px] text-[var(--ink-dim)]">{mirror ? 'Nothing matches.' : 'Sync to mirror the repo.'}</div>}
        </div>
      )}
        </>
      )}
    </div>
  );
}
