// ============================================================================
// Forge — per-agent knowledge & specialization. The honest three-layer model:
//   Knowledge Pack (RAG)  — uploaded docs in an isolated vector namespace
//   Adapter (LoRA/PEFT)   — domain skill baked into a small adapter on a base
//   Persona / Steering    — system prompt + octagon steering weights
// "Erase what it knows" = scope the pack + constrain the persona (+ optional
// domain adapter). Base-model latent knowledge is SCOPED/CONSTRAINED, not
// deleted — surfaced honestly in the UI. Pure assembly logic lives here.
// ============================================================================

export interface KnowledgePack {
  id: string;
  name: string;
  docs: { id: string; name: string; bytes: number; status: 'pending' | 'embedded' | 'error' }[];
  namespace: string; // server-side vector namespace
}

export interface Persona {
  id: string;
  name: string;
  systemPrompt: string;
  /** Octagon steering weights (reuses the Steer vector shape, optional). */
  steering?: Record<string, number>;
  /** Domain lock: refuse out-of-domain requests. */
  domainLock?: string;
}

export interface AdapterRef {
  id: string;
  name: string;
  baseModel: string;
  status: 'none' | 'training' | 'ready' | 'error';
  rank?: number;
}

export interface ForgeAgent {
  id: string;
  name: string;
  packId?: string;
  personaId?: string;
  adapterId?: string;
  fusionId?: string; // default fusion / model
}

/** Pure: assemble the full system context an agent runs with. The pack restricts
 *  retrieval; the persona constrains behavior; the adapter selects the model. */
export function assembleAgentContext(
  agent: ForgeAgent,
  packs: KnowledgePack[],
  personas: Persona[],
  adapters: AdapterRef[],
): {
  systemPrompt: string;
  model: string;
  retrievalNamespace: string | null;
  scoped: boolean;
} {
  const pack = packs.find((p) => p.id === agent.packId) ?? null;
  const persona = personas.find((p) => p.id === agent.personaId) ?? null;
  const adapter = adapters.find((a) => a.id === agent.adapterId) ?? null;

  const parts: string[] = [];
  if (persona?.systemPrompt) parts.push(persona.systemPrompt);
  if (persona?.domainLock) {
    parts.push(
      `You operate ONLY within: ${persona.domainLock}. If a request is outside this domain, decline and say it is out of scope.`,
    );
  }
  if (pack) {
    parts.push(
      `Answer strictly from the "${pack.name}" knowledge pack (retrieval namespace ${pack.namespace}). If the answer is not supported there, say so — do not rely on unrelated prior knowledge.`,
    );
  }

  const model = adapter && adapter.status === 'ready' ? `local/${adapter.id}` : agent.fusionId ?? 'openrouter/auto';
  return {
    systemPrompt: parts.join('\n\n'),
    model,
    retrievalNamespace: pack?.namespace ?? null,
    scoped: !!(pack || persona?.domainLock),
  };
}

/** Pure: scope a pack to an allowed subset of doc ids ("erase" the rest). */
export function scopePack(pack: KnowledgePack, allowedDocIds: string[]): KnowledgePack {
  return { ...pack, docs: pack.docs.filter((d) => allowedDocIds.includes(d.id)) };
}

// The worked C++ specialist trio (seed example) — one base, three specialists.
export function cppTrioSeed(): { packs: KnowledgePack[]; personas: Persona[]; adapters: AdapterRef[]; agents: ForgeAgent[] } {
  const base = 'qwen2.5-coder-14b';
  const mk = (slug: string, name: string, prompt: string, lock: string): [KnowledgePack, Persona, AdapterRef, ForgeAgent] => {
    const packId = `pack-${slug}`;
    const personaId = `persona-${slug}`;
    const adapterId = `cpp-${slug}`;
    return [
      { id: packId, name: `${name} pack`, docs: [], namespace: `ns-${slug}` },
      { id: personaId, name, systemPrompt: prompt, domainLock: lock },
      { id: adapterId, name: `cpp-${slug}`, baseModel: base, status: 'none', rank: 16 },
      // Default fusion falls back to a general model until the adapter is trained;
      // the pack + persona still scope the agent. assembleAgentContext switches to
      // local/<adapterId> once the adapter status is 'ready'.
      { id: `agent-${slug}`, name, packId, personaId, adapterId, fusionId: 'openrouter/auto' },
    ];
  };
  const trio = [
    mk('knowledge', 'C++ Knowledge', 'Answer only C++ language/stdlib questions; cite the standard.', 'C++ language and standard library'),
    mk('architecture', 'C++ Architect', 'Design C++ systems; produce module/interface plans, not implementation.', 'C++ system architecture and design'),
    mk('engineering', 'C++ Engineer', 'Implement and optimize C++; produce compiling code + tests.', 'C++ implementation and performance'),
  ];
  return {
    packs: trio.map((t) => t[0]),
    personas: trio.map((t) => t[1]),
    adapters: trio.map((t) => t[2]),
    agents: trio.map((t) => t[3]),
  };
}
