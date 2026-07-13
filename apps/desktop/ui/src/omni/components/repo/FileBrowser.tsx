import { useEffect, useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  fetchFullTree,
  getCachedTree,
  dirIndex,
  fetchFileContent,
  blobUrl,
  repoRef,
  RepoSyncError,
  type RepoTree,
  type DirChild,
  type FileContent,
} from '@/lib/repoSync';

function fmtSize(n?: number): string {
  if (!n && n !== 0) return '';
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

export function FileBrowser() {
  const [tree, setTree] = useState<RepoTree | null>(() => getCachedTree());
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [dir, setDir] = useState('');
  const [q, setQ] = useState('');
  const [open, setOpen] = useState<string | null>(null);

  const load = async (force: boolean) => {
    setLoading(true);
    setErr(null);
    try {
      setTree(await fetchFullTree(force));
    } catch (e) {
      setErr(e instanceof RepoSyncError ? e.message : 'Could not load the repo tree.');
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    void load(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const s = q.trim().toLowerCase();
  const children: DirChild[] = useMemo(() => (tree ? dirIndex(tree.entries, dir) : []), [tree, dir]);
  const searchResults: DirChild[] = useMemo(() => {
    if (!tree || !s) return [];
    return tree.entries
      .filter((e) => e.type === 'blob' && e.path.toLowerCase().includes(s))
      .slice(0, 200)
      .map((e) => ({ name: e.path, path: e.path, type: 'blob' as const, size: e.size }));
  }, [tree, s]);

  const crumbs = dir ? dir.split('/') : [];
  const total = tree?.entries.filter((e) => e.type === 'blob').length ?? 0;

  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <div className="mono text-[10px] text-[var(--ink-dim)]">{total ? `${total} files · entire repo` : loading ? 'loading tree…' : '—'}</div>
        <button onClick={() => void load(true)} className="mono text-[10px] text-[var(--octa-glow)]">↻ refresh</button>
      </div>

      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Search every file by path…"
        className="mb-2 w-full rounded-md border border-[var(--hairline)] bg-[var(--panel-solid)] px-3 py-2 text-[12px] text-[var(--ink)]"
      />

      {err && <div className="glass mb-2 px-3 py-2 text-[11px] text-[var(--state-error)]">{err}</div>}

      {!s && (
        <div className="mono mb-2 flex flex-wrap items-center gap-1 text-[11px]">
          <button onClick={() => setDir('')} className="text-[var(--octa-glow)]">root</button>
          {crumbs.map((c, i) => (
            <span key={i} className="flex items-center gap-1">
              <span className="text-[var(--ink-faint)]">/</span>
              <button onClick={() => setDir(crumbs.slice(0, i + 1).join('/'))} className="text-[var(--ink)]">{c}</button>
            </span>
          ))}
        </div>
      )}

      {loading && !tree ? (
        <div className="py-6 text-center text-[12px] text-[var(--ink-dim)]">Loading the full tree…</div>
      ) : (
        <div className="flex flex-col gap-1">
          {(s ? searchResults : children).map((c) => (
            <button
              key={c.path}
              onClick={() => (c.type === 'tree' ? (setDir(c.path), setQ('')) : setOpen(c.path))}
              className="glass flex items-center justify-between px-3 py-2 text-left active:scale-[0.99]"
            >
              <div className="flex min-w-0 items-center gap-2">
                <span className="shrink-0 text-[12px]">{c.type === 'tree' ? '📁' : '📄'}</span>
                <span className="mono truncate text-[12px] text-[var(--ink)]">{c.name}</span>
              </div>
              <span className="mono shrink-0 text-[9px] text-[var(--ink-faint)]">{c.type === 'tree' ? '›' : fmtSize(c.size)}</span>
            </button>
          ))}
          {!loading && (s ? searchResults : children).length === 0 && (
            <div className="py-6 text-center text-[11px] text-[var(--ink-dim)]">{tree ? 'Empty.' : 'Refresh to load the repo.'}</div>
          )}
        </div>
      )}

      <AnimatePresence>{open && <FileViewer path={open} onClose={() => setOpen(null)} />}</AnimatePresence>
    </div>
  );
}

function FileViewer({ path, onClose }: { path: string; onClose: () => void }) {
  const [content, setContent] = useState<FileContent | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const ref = repoRef();

  useEffect(() => {
    let alive = true;
    fetchFileContent(path)
      .then((c) => alive && setContent(c))
      .catch((e) => alive && setErr(e instanceof RepoSyncError ? e.message : 'Could not load file.'));
    return () => {
      alive = false;
    };
  }, [path]);

  return (
    <>
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose} className="fixed inset-0 z-[80] bg-black/70" />
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: 20 }}
        transition={{ type: 'spring', stiffness: 360, damping: 32 }}
        className="fixed inset-x-2 bottom-2 top-[8vh] z-[81] mx-auto flex max-w-2xl flex-col overflow-hidden rounded-2xl border border-[var(--hairline)] bg-[var(--bg-elev)]"
      >
        <div className="flex items-center justify-between border-b border-[var(--hairline)] px-3 py-2">
          <div className="mono min-w-0 truncate text-[11px] text-[var(--ink)]">{path}</div>
          <div className="flex shrink-0 items-center gap-3">
            <a href={blobUrl(ref, path)} target="_blank" rel="noreferrer" className="mono text-[10px] text-[var(--octa-glow)]">GitHub ↗</a>
            <button onClick={onClose} className="text-[16px] leading-none text-[var(--ink-dim)]">×</button>
          </div>
        </div>
        <div className="scroll-area flex-1 overflow-auto p-3">
          {err ? (
            <div className="text-[11px] text-[var(--state-error)]">{err}</div>
          ) : !content ? (
            <div className="text-center text-[12px] text-[var(--ink-dim)]">Loading…</div>
          ) : content.kind === 'image' ? (
            <img src={content.rawUrl} alt={path} className="mx-auto max-w-full rounded-md" />
          ) : content.kind === 'binary' ? (
            <div className="text-center text-[11px] text-[var(--ink-dim)]">
              Binary file — <a href={content.rawUrl} target="_blank" rel="noreferrer" className="text-[var(--octa-glow)]">download / open on GitHub</a>.
            </div>
          ) : (
            <pre className="mono whitespace-pre-wrap break-words text-[11px] leading-relaxed text-[var(--ink)]">{content.text}</pre>
          )}
        </div>
      </motion.div>
    </>
  );
}
