import { describe, it, expect } from 'vitest';
import {
  parsePlugins,
  parseProviders,
  parseSkills,
  parseOptionalMcps,
  parseDocs,
  parseMcpJson,
  mirrorCounts,
  syncStatus,
  dirIndex,
  fileKind,
  mapPull,
  type RepoRef,
  type RepoMirror,
  type TreeEntry,
} from '../src/lib/repoSync';

const ref: RepoRef = { owner: 'A-C-I-SOFTWARE-AND-DEVELOPMENT', repo: 'M.U.S.E', branch: 'main' };

const PATHS = [
  'plugins/memory/plugin.yaml',
  'plugins/memory/mem0/plugin.yaml',
  'plugins/github_assistant/plugin.yaml',
  'plugins/model-providers/anthropic/plugin.yaml',
  'plugins/model-providers/openai/plugin.yaml',
  'plugins/model-providers/openai-codex/plugin.yaml',
  'skills/jarvis-prime/SKILL.md',
  'skills/productivity/linear/SKILL.md',
  'optional-skills/mlops/pytorch/SKILL.md',
  'optional-mcps/github/README.md',
  'optional-mcps/github/server.py',
  'optional-mcps/context7/README.md',
  'docs/orchestration/README.md',
  'docs/architecture/muse-component-registry.yaml',
  'README.md',
  'run_agent.py',
];

describe('parsePlugins', () => {
  it('finds plugin.yaml folders but excludes model-providers', () => {
    const p = parsePlugins(ref, PATHS);
    const names = p.map((x) => x.name);
    expect(names).toContain('memory');
    expect(names).toContain('memory/mem0');
    expect(names).toContain('github_assistant');
    expect(names.some((n) => n.startsWith('model-providers'))).toBe(false);
    expect(p[0].url).toContain('github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/M.U.S.E/blob/main/');
  });
});

describe('parseProviders', () => {
  it('finds model-provider plugins', () => {
    const names = parseProviders(ref, PATHS).map((x) => x.name);
    expect(names).toEqual(['anthropic', 'openai', 'openai-codex']);
  });
});

describe('parseSkills', () => {
  it('finds SKILL.md across skills + optional-skills with category + optional flag', () => {
    const s = parseSkills(ref, PATHS);
    const linear = s.find((x) => x.name === 'linear');
    expect(linear?.category).toBe('productivity');
    expect(linear?.optional).toBeFalsy();
    const pytorch = s.find((x) => x.name === 'pytorch');
    expect(pytorch?.optional).toBe(true);
    const core = s.find((x) => x.name === 'jarvis-prime');
    expect(core?.category).toBe('core');
  });
});

describe('parseOptionalMcps', () => {
  it('dedupes optional-mcps to one entry per server dir', () => {
    const names = parseOptionalMcps(ref, PATHS).map((x) => x.name);
    expect(names).toEqual(['context7', 'github']);
  });
});

describe('parseDocs', () => {
  it('collects markdown under docs/ only', () => {
    const names = parseDocs(ref, PATHS).map((x) => x.name);
    expect(names).toContain('orchestration/README.md');
    expect(names).not.toContain('README.md'); // root readme is not under docs/
    // yaml under docs/ is not markdown
    expect(names.some((n) => n.endsWith('.yaml'))).toBe(false);
  });
});

describe('parseMcpJson', () => {
  it('parses .mcp.json into typed servers with transport inference', () => {
    const json = JSON.stringify({
      mcpServers: {
        filesystem: { command: 'npx', args: ['-y', 'server-filesystem'] },
        linear: { type: 'http', url: 'https://mcp.linear.app/mcp' },
        sentry: { url: 'https://mcp.sentry.dev/mcp' },
      },
    });
    const servers = parseMcpJson(json);
    expect(servers.map((s) => s.name)).toEqual(['filesystem', 'linear', 'sentry']);
    expect(servers.find((s) => s.name === 'filesystem')?.transport).toBe('stdio');
    expect(servers.find((s) => s.name === 'linear')?.transport).toBe('http');
    expect(servers.find((s) => s.name === 'sentry')?.transport).toBe('http');
  });
  it('returns [] on garbage', () => {
    expect(parseMcpJson('not json')).toEqual([]);
    expect(parseMcpJson('{}')).toEqual([]);
  });
});

describe('mirrorCounts + syncStatus', () => {
  it('counts each section', () => {
    const m = {
      ref,
      head: null,
      plugins: parsePlugins(ref, PATHS),
      providers: parseProviders(ref, PATHS),
      skills: parseSkills(ref, PATHS),
      optionalMcps: parseOptionalMcps(ref, PATHS),
      mcpServers: [],
      docs: parseDocs(ref, PATHS),
      truncated: false,
      fetchedAt: Date.now(),
    } as RepoMirror;
    const counts = Object.fromEntries(mirrorCounts(m).map((c) => [c.key, c.n]));
    expect(counts.providers).toBe(3);
    expect(counts.optionalMcps).toBe(2);
  });
  it('syncStatus is unknown without a head commit', () => {
    expect(syncStatus(null)).toBe('unknown');
  });
});

describe('dirIndex — full file browser', () => {
  const entries: TreeEntry[] = [
    { path: 'README.md', type: 'blob', size: 10 },
    { path: 'docs', type: 'tree' },
    { path: 'docs/orchestration', type: 'tree' },
    { path: 'docs/orchestration/README.md', type: 'blob', size: 20 },
    { path: 'docs/voice/guide.md', type: 'blob', size: 30 },
    { path: 'apps/nexus/src/main.tsx', type: 'blob', size: 40 },
  ];
  it('lists immediate children of root (folders first)', () => {
    const root = dirIndex(entries, '');
    expect(root.map((c) => c.name)).toEqual(['apps', 'docs', 'README.md']);
    expect(root[0].type).toBe('tree');
    expect(root.find((c) => c.name === 'README.md')?.type).toBe('blob');
  });
  it('descends into a subdirectory and dedupes nested folders', () => {
    const docs = dirIndex(entries, 'docs');
    expect(docs.map((c) => c.name)).toEqual(['orchestration', 'voice', ]);
    const orch = dirIndex(entries, 'docs/orchestration');
    expect(orch.map((c) => c.name)).toEqual(['README.md']);
    expect(orch[0].path).toBe('docs/orchestration/README.md');
  });
});

describe('fileKind', () => {
  it('classifies text, image, binary, and extensionless', () => {
    expect(fileKind('src/main.tsx')).toBe('text');
    expect(fileKind('README.md')).toBe('text');
    expect(fileKind('LICENSE')).toBe('text'); // extensionless → text
    expect(fileKind('docs/diagram.png')).toBe('image');
    expect(fileKind('app/icon.svg')).toBe('text'); // svg is text/markup
    expect(fileKind('bin/tool.wasm')).toBe('binary');
  });
});

describe('mapPull — PR history', () => {
  it('maps merged / open / closed correctly', () => {
    const merged = mapPull({ number: 1, title: 'first', state: 'closed', merged_at: '2024-01-01T00:00:00Z', created_at: '2023-12-31T00:00:00Z', user: { login: 'jeremiah' }, base: { ref: 'main' }, html_url: 'u1' });
    expect(merged.merged).toBe(true);
    expect(merged.baseRef).toBe('main');
    const open = mapPull({ number: 2, title: 'wip', state: 'open', merged_at: null, created_at: '2024-02-01T00:00:00Z', user: { login: 'x' }, base: { ref: 'main' }, html_url: 'u2' });
    expect(open.state).toBe('open');
    expect(open.merged).toBe(false);
    const closed = mapPull({ number: 3, title: 'rejected', state: 'closed', merged_at: null, created_at: '2024-03-01T00:00:00Z', user: null, base: { ref: 'main' }, html_url: 'u3' });
    expect(closed.merged).toBe(false);
    expect(closed.user).toBe('');
  });
});
