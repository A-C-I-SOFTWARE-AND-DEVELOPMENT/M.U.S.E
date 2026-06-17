import type {
  AgentStatus,
  AgentSummary,
  AgentSurface,
  SteeringVector,
} from '@/lib/types';

// ============================================================================
// Surface adapters. All three surfaces implement AgentSurface so the UI never
// branches on vendor. Only M.U.S.E. embeds + applies steering; Antigravity and
// AI Studio are LINK-OUT only (see note in antigravity.ts).
// ============================================================================

const MUSE_BASE = import.meta.env.VITE_MUSE_BASE_URL ?? '';

/** M.U.S.E. adapter — the deep integration (the only backend the user owns). */
export const museSurface: AgentSurface = {
  id: 'muse',
  kind: 'muse',
  canEmbed: true, // user controls the CSP -> embeddable in-app.
  async listAgents(): Promise<AgentSummary[]> {
    if (!MUSE_BASE) return []; // honest empty state when unconfigured.
    try {
      const res = await fetch(`${MUSE_BASE}/api/agents`);
      if (!res.ok) throw new Error(String(res.status));
      const data = (await res.json()) as AgentSummary[];
      return data.map((a) => ({ ...a, surface: 'muse' }));
    } catch {
      return [];
    }
  },
  async getStatus(agentId: string): Promise<AgentStatus> {
    if (!MUSE_BASE)
      return { id: agentId, state: 'unknown', updatedAt: Date.now() };
    try {
      const res = await fetch(`${MUSE_BASE}/api/agents/${agentId}/status`);
      return (await res.json()) as AgentStatus;
    } catch {
      return { id: agentId, state: 'unknown', updatedAt: Date.now() };
    }
  },
  async applySteering(agentId: string, v: SteeringVector): Promise<void> {
    if (!MUSE_BASE) return;
    // Sends the octagon's steering vector to M.U.S.E.'s model-routing layer.
    // Endpoint shape documented in ADAPTERS.md.
    await fetch(`${MUSE_BASE}/api/agents/${agentId}/steer`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(v),
    });
  },
};

/**
 * Antigravity adapter — LINK-OUT ONLY.
 *
 * IMPORTANT (do not "fix" by iframing): Antigravity sends X-Frame-Options /
 * restrictive frame-ancestors CSP and refuses to render inside an iframe.
 * There is no embeddable SDK. We deep-link out instead.
 */
export const antigravitySurface: AgentSurface = {
  id: 'antigravity',
  kind: 'antigravity',
  canEmbed: false,
  async listAgents() {
    return [
      {
        id: 'antigravity-preview',
        name: 'Antigravity Agent Preview',
        surface: 'antigravity',
        role: 'antigravity-preview-05-2026',
        state: 'unknown',
      },
    ];
  },
  async getStatus(agentId) {
    return { id: agentId, state: 'unknown', updatedAt: Date.now() };
  },
  openExternal() {
    window.open('https://antigravity.google/', '_blank', 'noopener,noreferrer');
  },
};

/**
 * AI Studio adapter — LINK-OUT ONLY (same CSP/frame-ancestors reason as above).
 */
export const aiStudioSurface: AgentSurface = {
  id: 'aistudio',
  kind: 'aistudio',
  canEmbed: false,
  async listAgents() {
    return [
      { id: 'aistudio-chat', name: 'AI Studio Playground', surface: 'aistudio', state: 'unknown' },
    ];
  },
  async getStatus(agentId) {
    return { id: agentId, state: 'unknown', updatedAt: Date.now() };
  },
  openExternal() {
    window.open(
      'https://aistudio.google.com/prompts/new_chat',
      '_blank',
      'noopener,noreferrer',
    );
  },
};

export const surfaces: AgentSurface[] = [
  museSurface,
  antigravitySurface,
  aiStudioSurface,
];
