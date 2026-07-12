// ============================================================================
// Live MUSE repo mirror. NEXUS reflects whatever is on the MUSE `main` branch on
// GitHub — its plugins, model providers, skills, MCP servers, and docs — by
// reading the repo directly from the GitHub API at runtime. One recursive
// git-trees request returns the whole file tree; `.mcp.json` is fetched raw for
// the authoritative MCP server registry. No build step, no server, no extra deps
// (JSON only — never an in-browser YAML parser). Everything is derived from the
// repo's own conventions so the app stays a true mirror of `main`.
//
//   plugins/<name>/plugin.yaml                  → plugins
//   plugins/model-providers/<name>/plugin.yaml  → model providers
//   skills/**/SKILL.md · optional-skills/**      → skills
//   optional-mcps/<name>/…                       → optional MCP servers
//   .mcp.json  { mcpServers: { … } }             → connected MCP servers
//   docs/**/*.md                                 → docs
//
// All network access degrades honestly: cached mirror on offline / rate-limit,
// typed errors surfaced to the UI, optional GITHUB_TOKEN to lift the anon limit.
// ============================================================================

import { getSecret, getConfig, setConfig } from './config';

export interface RepoRef {
  owner: string;
  repo: string;
  branch: string;
}

export interface HeadCommit {
  sha: string;
  shortSha: string;
  message: string;
  author: string;
  date: string;
  url: string;
}

export interface RepoItem {
  id: string;
  name: string;
  path: string;
  category?: string;
  optional?: boolean;
  url: string; // GitHub blob URL
}

export type McpTransport = 'http' | 'sse' | 'stdio';
export interface McpServer {
  name: string;
  transport: McpTransport;
  url?: string;
  command?: string;
  optional?: boolean;
}

export interface RepoMirror {
  ref: RepoRef;
  head: HeadCommit | null;
  plugins: RepoItem[];
  providers: RepoItem[];
  skills: RepoItem[];
  optionalMcps: RepoItem[];
  mcpServers: McpServer[];
  docs: RepoItem[];
  truncated: boolean;
  fetchedAt: number;
}

export interface BuildInfo {
  sha: string;
  time: string;
}

const DEFAULT_SLUG = (typeof __REPO_SLUG__ !== 'undefined' && __REPO_SLUG__) || 'A-C-I-SOFTWARE-AND-DEVELOPMENT/M.U.S.E';
const CACHE_KEY = 'nexus.repo.mirror.v1';
const TTL_MS = 30 * 60 * 1000; // 30 min

// ---- repo ref (configurable; defaults to the canonical MUSE repo) -----------
export function repoRef(): RepoRef {
  const cfg = getConfig();
  const slug = (cfg.repoSlug || DEFAULT_SLUG).trim().replace(/^https?:\/\/github\.com\//i, '').replace(/\.git$/, '');
  const [owner, repo] = slug.split('/');
  return { owner: owner || 'A-C-I-SOFTWARE-AND-DEVELOPMENT', repo: repo || 'M.U.S.E', branch: cfg.repoBranch || 'main' };
}

export function setRepoRef(patch: { repoSlug?: string; repoBranch?: string }): void {
  setConfig(patch);
}

export function buildInfo(): BuildInfo {
  return {
    sha: (typeof __BUILD_SHA__ !== 'undefined' && __BUILD_SHA__) || 'dev',
    time: (typeof __BUILD_TIME__ !== 'undefined' && __BUILD_TIME__) || '',
  };
}

export function blobUrl(ref: RepoRef, path: string): string {
  return `https://github.com/${ref.owner}/${ref.repo}/blob/${ref.branch}/${path}`;
}
export function rawUrl(ref: RepoRef, path: string): string {
  return `https://raw.githubusercontent.com/${ref.owner}/${ref.repo}/${ref.branch}/${path}`;
}

function ghHeaders(): Record<string, string> {
  const h: Record<string, string> = { Accept: 'application/vnd.github+json' };
  const token = getSecret('GITHUB_TOKEN');
  if (token) h.Authorization = `Bearer ${token}`;
  return h;
}

// ---- pure parsers (unit-tested) ---------------------------------------------
// Each takes the flat list of repo paths from the recursive tree.

export function parsePlugins(ref: RepoRef, paths: string[]): RepoItem[] {
  const out: RepoItem[] = [];
  for (const p of paths) {
    const m = p.match(/^plugins\/(.+)\/plugin\.yaml$/);
    if (!m || m[1].startsWith('model-providers/')) continue;
    out.push({ id: `plugin:${m[1]}`, name: m[1], path: p, url: blobUrl(ref, p) });
  }
  return out.sort((a, b) => a.name.localeCompare(b.name));
}

export function parseProviders(ref: RepoRef, paths: string[]): RepoItem[] {
  const out: RepoItem[] = [];
  for (const p of paths) {
    const m = p.match(/^plugins\/model-providers\/([^/]+)\/plugin\.yaml$/);
    if (!m) continue;
    out.push({ id: `provider:${m[1]}`, name: m[1], path: p, url: blobUrl(ref, p) });
  }
  return out.sort((a, b) => a.name.localeCompare(b.name));
}

export function parseSkills(ref: RepoRef, paths: string[]): RepoItem[] {
  const out: RepoItem[] = [];
  for (const p of paths) {
    const m = p.match(/^(optional-skills|skills)\/(.+)\/SKILL\.md$/);
    if (!m) continue;
    const rel = m[2];
    const category = rel.includes('/') ? rel.split('/')[0] : 'core';
    const name = rel.split('/').pop() || rel;
    out.push({ id: `skill:${m[1]}/${rel}`, name, path: p, category, optional: m[1] === 'optional-skills', url: blobUrl(ref, p) });
  }
  return out.sort((a, b) => a.name.localeCompare(b.name));
}

export function parseOptionalMcps(ref: RepoRef, paths: string[]): RepoItem[] {
  const seen = new Set<string>();
  const out: RepoItem[] = [];
  for (const p of paths) {
    const m = p.match(/^optional-mcps\/([^/]+)\//);
    if (!m || seen.has(m[1])) continue;
    seen.add(m[1]);
    out.push({ id: `omcp:${m[1]}`, name: m[1], path: `optional-mcps/${m[1]}`, optional: true, url: blobUrl(ref, `optional-mcps/${m[1]}`) });
  }
  return out.sort((a, b) => a.name.localeCompare(b.name));
}

export function parseDocs(ref: RepoRef, paths: string[]): RepoItem[] {
  const out: RepoItem[] = [];
  for (const p of paths) {
    if (!/^docs\/.+\.md$/i.test(p)) continue;
    const name = p.replace(/^docs\//, '');
    out.push({ id: `doc:${p}`, name, path: p, url: blobUrl(ref, p) });
  }
  return out.sort((a, b) => a.name.localeCompare(b.name));
}

/** Parse the root `.mcp.json` into the connected MCP server registry. */
export function parseMcpJson(text: string): McpServer[] {
  let obj: unknown;
  try {
    obj = JSON.parse(text);
  } catch {
    return [];
  }
  const servers = (obj as { mcpServers?: Record<string, unknown> })?.mcpServers;
  if (!servers || typeof servers !== 'object') return [];
  return Object.entries(servers)
    .map(([name, raw]) => {
      const cfg = (raw ?? {}) as { type?: string; url?: string; command?: string };
      const transport: McpTransport = cfg.type === 'sse' ? 'sse' : cfg.url || cfg.type === 'http' ? 'http' : 'stdio';
      return { name, transport, url: cfg.url, command: cfg.command };
    })
    .sort((a, b) => a.name.localeCompare(b.name));
}

// ---- cache ------------------------------------------------------------------
export function getCachedMirror(): RepoMirror | null {
  try {
    const raw = localStorage.getItem(CACHE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as RepoMirror;
  } catch {
    return null;
  }
}

function cacheMirror(m: RepoMirror): void {
  try {
    localStorage.setItem(CACHE_KEY, JSON.stringify(m));
  } catch {
    /* ignore quota */
  }
}

export function clearMirrorCache(): void {
  try {
    localStorage.removeItem(CACHE_KEY);
  } catch {
    /* ignore */
  }
}

export class RepoSyncError extends Error {
  constructor(
    message: string,
    readonly kind: 'rate-limit' | 'not-found' | 'network' | 'http',
  ) {
    super(message);
    this.name = 'RepoSyncError';
  }
}

// ---- live fetch -------------------------------------------------------------
async function fetchHead(ref: RepoRef, signal?: AbortSignal): Promise<HeadCommit> {
  const res = await fetch(`https://api.github.com/repos/${ref.owner}/${ref.repo}/commits/${ref.branch}`, {
    headers: ghHeaders(),
    signal,
  }).catch((e) => {
    throw new RepoSyncError(`Network error: ${e?.message ?? e}`, 'network');
  });
  if (res.status === 403 && res.headers.get('x-ratelimit-remaining') === '0')
    throw new RepoSyncError('GitHub API rate limit reached. Add a GITHUB_TOKEN in Settings to lift it.', 'rate-limit');
  if (res.status === 404) throw new RepoSyncError('Repository or branch not found.', 'not-found');
  if (!res.ok) throw new RepoSyncError(`GitHub responded ${res.status}.`, 'http');
  const j = (await res.json()) as {
    sha: string;
    html_url: string;
    commit: { message: string; author: { name: string; date: string } };
  };
  return {
    sha: j.sha,
    shortSha: j.sha.slice(0, 7),
    message: (j.commit?.message ?? '').split('\n')[0],
    author: j.commit?.author?.name ?? '',
    date: j.commit?.author?.date ?? '',
    url: j.html_url,
  };
}

async function fetchTreePaths(ref: RepoRef, treeish: string, signal?: AbortSignal): Promise<{ paths: string[]; truncated: boolean }> {
  const res = await fetch(`https://api.github.com/repos/${ref.owner}/${ref.repo}/git/trees/${treeish}?recursive=1`, {
    headers: ghHeaders(),
    signal,
  }).catch((e) => {
    throw new RepoSyncError(`Network error: ${e?.message ?? e}`, 'network');
  });
  if (res.status === 403 && res.headers.get('x-ratelimit-remaining') === '0')
    throw new RepoSyncError('GitHub API rate limit reached. Add a GITHUB_TOKEN in Settings to lift it.', 'rate-limit');
  if (!res.ok) throw new RepoSyncError(`GitHub responded ${res.status}.`, 'http');
  const j = (await res.json()) as { tree: { path: string; type: string }[]; truncated: boolean };
  return { paths: (j.tree ?? []).filter((t) => t.type === 'blob' || t.type === 'tree').map((t) => t.path), truncated: !!j.truncated };
}

async function fetchMcpJson(ref: RepoRef, signal?: AbortSignal): Promise<McpServer[]> {
  try {
    const res = await fetch(rawUrl(ref, '.mcp.json'), { signal });
    if (!res.ok) return [];
    return parseMcpJson(await res.text());
  } catch {
    return [];
  }
}

/**
 * Fetch (or return cached) the live mirror of MUSE `main`. One commit lookup +
 * one recursive tree + the raw `.mcp.json`. Falls back to cache on any error.
 */
export async function fetchMirror(force = false, signal?: AbortSignal): Promise<RepoMirror> {
  const cached = getCachedMirror();
  if (!force && cached && Date.now() - cached.fetchedAt < TTL_MS) return cached;

  const ref = repoRef();
  try {
    const head = await fetchHead(ref, signal);
    const [{ paths, truncated }, mcpServers] = await Promise.all([fetchTreePaths(ref, head.sha, signal), fetchMcpJson(ref, signal)]);
    const optionalMcps = parseOptionalMcps(ref, paths);
    // Mark which connected servers are also present as optional bundles.
    const optionalNames = new Set(optionalMcps.map((o) => o.name));
    for (const s of mcpServers) if (optionalNames.has(s.name)) s.optional = true;

    const mirror: RepoMirror = {
      ref,
      head,
      plugins: parsePlugins(ref, paths),
      providers: parseProviders(ref, paths),
      skills: parseSkills(ref, paths),
      optionalMcps,
      mcpServers,
      docs: parseDocs(ref, paths),
      truncated,
      fetchedAt: Date.now(),
    };
    cacheMirror(mirror);
    return mirror;
  } catch (err) {
    if (cached) return cached; // honest stale-while-error
    throw err;
  }
}

// ============================================================================
// Full file tree — the entire repo, end-to-end, file to file. Lazy-loaded (only
// when the Files browser opens) and cached under its own key keyed by HEAD sha.
// ============================================================================

export interface TreeEntry {
  path: string;
  type: 'blob' | 'tree';
  size?: number;
}
export interface RepoTree {
  sha: string;
  entries: TreeEntry[];
  truncated: boolean;
  fetchedAt: number;
}
export interface DirChild {
  name: string;
  path: string;
  type: 'blob' | 'tree';
  size?: number;
}

const TREE_KEY = 'nexus.repo.tree.v1';

/** Immediate children (folders first, then files) of a directory `prefix`. Pure. */
export function dirIndex(entries: TreeEntry[], prefix: string): DirChild[] {
  const base = prefix ? prefix.replace(/\/+$/, '') + '/' : '';
  const seen = new Map<string, DirChild>();
  for (const e of entries) {
    if (base && !e.path.startsWith(base)) continue;
    const rest = e.path.slice(base.length);
    if (!rest) continue;
    const slash = rest.indexOf('/');
    if (slash === -1) {
      if (e.type === 'blob') seen.set(rest, { name: rest, path: e.path, type: 'blob', size: e.size });
      else if (!seen.has(rest)) seen.set(rest, { name: rest, path: e.path, type: 'tree' });
    } else {
      const dir = rest.slice(0, slash);
      if (!seen.has(dir)) seen.set(dir, { name: dir, path: base + dir, type: 'tree' });
    }
  }
  return [...seen.values()].sort((a, b) =>
    a.type !== b.type ? (a.type === 'tree' ? -1 : 1) : a.name.localeCompare(b.name),
  );
}

export function getCachedTree(): RepoTree | null {
  try {
    const raw = localStorage.getItem(TREE_KEY);
    return raw ? (JSON.parse(raw) as RepoTree) : null;
  } catch {
    return null;
  }
}

export async function fetchFullTree(force = false, signal?: AbortSignal): Promise<RepoTree> {
  const ref = repoRef();
  const cached = getCachedTree();
  // Reuse cache if it matches the current cached mirror HEAD (or within TTL).
  const head = getCachedMirror()?.head?.sha;
  if (!force && cached && (!head || cached.sha === head) && Date.now() - cached.fetchedAt < TTL_MS) return cached;

  const treeish = head || ref.branch;
  const res = await fetch(`https://api.github.com/repos/${ref.owner}/${ref.repo}/git/trees/${treeish}?recursive=1`, {
    headers: ghHeaders(),
    signal,
  }).catch((e) => {
    throw new RepoSyncError(`Network error: ${e?.message ?? e}`, 'network');
  });
  if (res.status === 403 && res.headers.get('x-ratelimit-remaining') === '0')
    throw new RepoSyncError('GitHub API rate limit reached. Add a GITHUB_TOKEN in Settings to lift it.', 'rate-limit');
  if (!res.ok) throw new RepoSyncError(`GitHub responded ${res.status}.`, 'http');
  const j = (await res.json()) as { sha: string; tree: TreeEntry[]; truncated: boolean };
  const tree: RepoTree = {
    sha: j.sha,
    entries: (j.tree ?? []).filter((t) => t.type === 'blob' || t.type === 'tree').map((t) => ({ path: t.path, type: t.type, size: t.size })),
    truncated: !!j.truncated,
    fetchedAt: Date.now(),
  };
  try {
    localStorage.setItem(TREE_KEY, JSON.stringify(tree));
  } catch {
    /* tree too big for quota → still return in-memory */
  }
  return tree;
}

const TEXT_EXT = /\.(md|markdown|txt|py|ts|tsx|js|jsx|mjs|cjs|json|ya?ml|toml|ini|cfg|conf|sh|bash|zsh|env|gitignore|dockerfile|rs|go|java|kt|kts|c|h|cpp|hpp|cs|rb|php|swift|sql|html|css|scss|xml|csv|tsv|gradle|properties|lock|mk|cmake|gql|graphql|proto|svg|R|jl|lua|pl|vue|astro|tf|hcl|bat|ps1|patch|diff|text|rst|adoc|org)$/i;
const IMAGE_EXT = /\.(png|jpe?g|gif|webp|bmp|ico|avif)$/i;

export function fileKind(path: string): 'text' | 'image' | 'binary' {
  const name = path.split('/').pop() ?? path;
  if (IMAGE_EXT.test(name)) return 'image';
  if (TEXT_EXT.test(name) || !name.includes('.')) return 'text'; // extensionless (LICENSE, Makefile…) → text
  return 'binary';
}

export interface FileContent {
  path: string;
  kind: 'text' | 'image' | 'binary';
  text?: string;
  rawUrl: string;
  size: number;
}

const MAX_TEXT_BYTES = 400 * 1024;

export async function fetchFileContent(path: string, signal?: AbortSignal): Promise<FileContent> {
  const ref = repoRef();
  const url = rawUrl(ref, path);
  const kind = fileKind(path);
  if (kind !== 'text') return { path, kind, rawUrl: url, size: 0 };
  const res = await fetch(url, { signal, headers: getSecret('GITHUB_TOKEN') ? { Authorization: `Bearer ${getSecret('GITHUB_TOKEN')}` } : {} }).catch((e) => {
    throw new RepoSyncError(`Network error: ${e?.message ?? e}`, 'network');
  });
  if (res.status === 404) throw new RepoSyncError('File not found.', 'not-found');
  if (!res.ok) throw new RepoSyncError(`GitHub responded ${res.status}.`, 'http');
  const text = await res.text();
  const truncated = text.length > MAX_TEXT_BYTES;
  return { path, kind: 'text', text: truncated ? text.slice(0, MAX_TEXT_BYTES) + '\n\n… (truncated — open on GitHub for the full file)' : text, rawUrl: url, size: text.length };
}

// ============================================================================
// Pull request history — every PR from #1 to the latest. All merges to `main`
// move HEAD, which the mirror reflects on the next sync.
// ============================================================================

export interface PullRequest {
  number: number;
  title: string;
  state: 'open' | 'closed';
  merged: boolean;
  mergedAt?: string;
  createdAt: string;
  user: string;
  baseRef: string;
  url: string;
}

interface RawPull {
  number: number;
  title: string;
  state: string;
  merged_at: string | null;
  created_at: string;
  user: { login: string } | null;
  base: { ref: string };
  html_url: string;
}

export function mapPull(j: RawPull): PullRequest {
  return {
    number: j.number,
    title: j.title,
    state: j.state === 'open' ? 'open' : 'closed',
    merged: !!j.merged_at,
    mergedAt: j.merged_at ?? undefined,
    createdAt: j.created_at,
    user: j.user?.login ?? '',
    baseRef: j.base?.ref ?? '',
    url: j.html_url,
  };
}

export interface PullPage {
  pulls: PullRequest[];
  hasMore: boolean;
  page: number;
}

/** Fetch one page of PRs, oldest-first (#1 → latest), state=all. */
export async function fetchPulls(page = 1, perPage = 50, signal?: AbortSignal): Promise<PullPage> {
  const ref = repoRef();
  const res = await fetch(
    `https://api.github.com/repos/${ref.owner}/${ref.repo}/pulls?state=all&sort=created&direction=asc&per_page=${perPage}&page=${page}`,
    { headers: ghHeaders(), signal },
  ).catch((e) => {
    throw new RepoSyncError(`Network error: ${e?.message ?? e}`, 'network');
  });
  if (res.status === 403 && res.headers.get('x-ratelimit-remaining') === '0')
    throw new RepoSyncError('GitHub API rate limit reached. Add a GITHUB_TOKEN in Settings to lift it.', 'rate-limit');
  if (!res.ok) throw new RepoSyncError(`GitHub responded ${res.status}.`, 'http');
  const arr = (await res.json()) as RawPull[];
  return { pulls: arr.map(mapPull), hasMore: arr.length === perPage, page };
}

export function mirrorCounts(m: RepoMirror): { key: string; label: string; n: number }[] {
  return [
    { key: 'plugins', label: 'Plugins', n: m.plugins.length },
    { key: 'providers', label: 'Model providers', n: m.providers.length },
    { key: 'skills', label: 'Skills', n: m.skills.length },
    { key: 'mcpServers', label: 'MCP servers', n: m.mcpServers.length },
    { key: 'optionalMcps', label: 'Optional MCPs', n: m.optionalMcps.length },
    { key: 'docs', label: 'Docs', n: m.docs.length },
  ];
}

/** Whether the running build matches the latest `main` HEAD. */
export function syncStatus(head: HeadCommit | null): 'current' | 'behind' | 'unknown' {
  const b = buildInfo();
  if (!head || !b.sha || b.sha === 'dev') return 'unknown';
  return head.sha.startsWith(b.sha) || b.sha.startsWith(head.shortSha) ? 'current' : 'behind';
}
