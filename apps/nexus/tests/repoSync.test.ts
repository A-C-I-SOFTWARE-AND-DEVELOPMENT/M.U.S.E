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
  type RepoRef,
  type RepoMirror,
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
