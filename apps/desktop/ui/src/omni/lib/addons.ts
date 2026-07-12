// ============================================================================
// Add-ons — the full MUSE integration surface, user-extensible. Mirrors the
// MUSE repo's CLI lanes and MCP servers, plus an "add your own" path for custom
// providers / MCP servers / CLIs. These run gateway-side (MUSE), so values are
// stored encrypted on-device and exported to ~/.hermes/.env via the credentials
// manager — NEXUS is the configuration surface.
// ============================================================================

import { getSecret, setSecret } from './config';
import type { McpServer, RepoItem } from './repoSync';

export type AddOnKind = 'provider' | 'mcp' | 'cli';

export interface AddOnField {
  env: string;
  label: string;
  type: 'text' | 'password' | 'url';
  placeholder?: string;
}

export interface AddOn {
  id: string;
  label: string;
  kind: AddOnKind;
  blurb: string;
  fields: AddOnField[];
  custom?: boolean;
}

// ---- MCP servers (mirror MUSE's connected MCP set) ---------------------------
export const MCP_SERVERS: AddOn[] = [
  ['github', 'GitHub', 'Repos, PRs, issues, Actions', 'GITHUB_MCP_TOKEN'],
  ['slack', 'Slack', 'Channels, messages, canvases', 'SLACK_MCP_TOKEN'],
  ['supabase', 'Supabase', 'Postgres, edge functions, advisors', 'SUPABASE_MCP_TOKEN'],
  ['vercel', 'Vercel', 'Deployments, projects, logs', 'VERCEL_MCP_TOKEN'],
  ['cloudflare', 'Cloudflare', 'D1, KV, R2, Workers', 'CLOUDFLARE_MCP_TOKEN'],
  ['notion', 'Notion', 'Pages, databases, search', 'NOTION_MCP_TOKEN'],
  ['linear', 'Linear', 'Issues, projects, cycles', 'LINEAR_MCP_TOKEN'],
  ['figma', 'Figma', 'Designs, code connect, assets', 'FIGMA_MCP_TOKEN'],
  ['gmail', 'Gmail', 'Threads, drafts, labels', 'GMAIL_MCP_TOKEN'],
  ['gdrive', 'Google Drive', 'Files, search, content', 'GDRIVE_MCP_TOKEN'],
  ['sentry', 'Sentry', 'Issues, traces', 'SENTRY_MCP_TOKEN'],
  ['postman', 'Postman', 'Collections, specs, mocks', 'POSTMAN_MCP_TOKEN'],
  ['context7', 'Context7', 'Live library docs', 'CONTEXT7_MCP_TOKEN'],
  ['exa', 'Exa', 'Web search + fetch', 'EXA_MCP_TOKEN'],
  ['firebase', 'Firebase', 'Apps, rules, deploy', 'FIREBASE_MCP_TOKEN'],
  ['gcs', 'Google Cloud Storage', 'Buckets, objects', 'GCS_MCP_TOKEN'],
].map(([id, label, blurb, env]) => ({
  id: `mcp-${id}`, label, kind: 'mcp' as const, blurb,
  fields: [
    { env: `${(env as string).replace('_TOKEN', '_URL')}`, label: 'Server URL / command', type: 'url' as const, placeholder: 'https://… or stdio command' },
    { env: env as string, label: 'Auth token (optional)', type: 'password' as const },
  ],
}));

// ---- CLI lanes (mirror MUSE's worker/CLI providers) --------------------------
export const CLI_LANES: AddOn[] = [
  ['claude-code', 'Claude Code', 'Primary builder lane', 'CLAUDE_CODE'],
  ['codex', 'OpenAI Codex', 'Reviewer / bounded-fix lane', 'CODEX'],
  ['gemini-cli', 'Gemini CLI', 'Google Code Assist lane', 'GEMINI_CLI'],
  ['qwen-cli', 'Qwen Code CLI', 'Qwen coding lane', 'QWEN_CLI'],
  ['cursor', 'Cursor Agent', 'Cursor CLI lane', 'CURSOR_CLI'],
  ['opencode', 'OpenCode', 'OpenCode Zen/Go lane', 'OPENCODE_CLI'],
  ['kilo', 'Kilo Code', 'Kilo gateway lane', 'KILO_CLI'],
  ['aider', 'Aider', 'Local pair-programmer lane', 'AIDER_CLI'],
  ['github-copilot', 'GitHub Copilot', 'copilot --acp lane', 'COPILOT_CLI'],
].map(([id, label, blurb, env]) => ({
  id: `cli-${id}`, label, kind: 'cli' as const, blurb,
  fields: [
    { env: `${env}_CMD`, label: 'Command / path', type: 'text' as const, placeholder: `${id} (in PATH)` },
    { env: `${env}_AUTH`, label: 'Auth / token (optional)', type: 'password' as const },
  ],
}));

// ---- Live add-ons derived from the MUSE repo mirror --------------------------
// When a repo mirror is cached (RepoSyncCard / RepoPage), the add-ons surface
// reflects the *actual* MCP servers declared on `main` (.mcp.json + optional-mcps)
// rather than a hand-picked list. Each gets a name-derived env pair so users can
// supply a URL/command + token. Falls back to MCP_SERVERS offline.

function mcpEnv(name: string): string {
  return name.toUpperCase().replace(/[^A-Z0-9]+/g, '_').replace(/^_|_$/g, '');
}

export function mcpAddon(name: string, blurb: string, optional = false): AddOn {
  const E = mcpEnv(name);
  return {
    id: `mcp-${name}`,
    label: name,
    kind: 'mcp',
    blurb,
    fields: [
      { env: `${E}_MCP_URL`, label: 'Server URL / command', type: 'url', placeholder: 'https://… or stdio command' },
      { env: `${E}_MCP_TOKEN`, label: optional ? 'Auth token (optional)' : 'Auth token', type: 'password' },
    ],
  };
}

/** Merge the connected (.mcp.json) + optional MCP servers from the live mirror. */
export function liveMcpAddons(servers: McpServer[], optional: RepoItem[]): AddOn[] {
  const out = new Map<string, AddOn>();
  for (const s of servers) {
    const blurb = s.url ? `${s.transport} · ${s.url}` : s.command ? `stdio · ${s.command}` : s.transport;
    out.set(s.name.toLowerCase(), mcpAddon(s.name, blurb, s.optional));
  }
  for (const o of optional) {
    const key = o.name.toLowerCase();
    if (!out.has(key)) out.set(key, mcpAddon(o.name, 'Optional MCP server (bundled in repo)', true));
  }
  return [...out.values()].sort((a, b) => a.label.localeCompare(b.label));
}

// ---- Custom add-ons (add your own) -------------------------------------------
const CUSTOM_KEY = 'nexus.addons.custom.v1';

export function getCustomAddons(): AddOn[] {
  try { return JSON.parse(localStorage.getItem(CUSTOM_KEY) ?? '[]'); } catch { return []; }
}
function persistCustom(list: AddOn[]) {
  try { localStorage.setItem(CUSTOM_KEY, JSON.stringify(list)); } catch { /* ignore */ }
  if (typeof window !== 'undefined') window.dispatchEvent(new CustomEvent('nexus:config'));
}

/** Add a custom provider / MCP / CLI with a base/url + key. */
export function addCustomAddon(kind: AddOnKind, label: string): AddOn {
  const slug = label.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'addon';
  const PREFIX = `CUSTOM_${kind.toUpperCase()}_${slug.toUpperCase().replace(/-/g, '_')}`;
  const addon: AddOn = {
    id: `custom-${kind}-${Date.now().toString(36)}`,
    label,
    kind,
    custom: true,
    blurb: `Your custom ${kind}.`,
    fields:
      kind === 'cli'
        ? [
            { env: `${PREFIX}_CMD`, label: 'Command / path', type: 'text', placeholder: 'my-cli --flag' },
            { env: `${PREFIX}_AUTH`, label: 'Auth / token (optional)', type: 'password' },
          ]
        : [
            { env: `${PREFIX}_URL`, label: kind === 'provider' ? 'Base URL (OpenAI-compatible)' : 'Server URL / command', type: 'url', placeholder: 'https://…/v1' },
            { env: `${PREFIX}_KEY`, label: 'API key / token', type: 'password' },
          ],
  };
  persistCustom([...getCustomAddons(), addon]);
  return addon;
}

export function removeCustomAddon(id: string): void {
  const list = getCustomAddons();
  const gone = list.find((a) => a.id === id);
  gone?.fields.forEach((f) => setSecret(f.env, ''));
  persistCustom(list.filter((a) => a.id !== id));
}

export function addonConfigured(a: AddOn): boolean {
  return a.fields.some((f) => getSecret(f.env));
}
