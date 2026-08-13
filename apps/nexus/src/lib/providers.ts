// ============================================================================
// Provider registry — mirrors MUSE's multi-provider model layer. Each provider
// is an OpenAI-compatible (or adapted) endpoint reachable with the user's own
// key. Browser-CORS-friendly providers run direct from the PWA (no server);
// the rest auto-route to the next best transport (OpenRouter → gateway).
//
// Keys are read from the encrypted credentials store (src/lib/config.ts) by the
// canonical env name, matching MUSE's ~/.hermes/.env conventions.
// ============================================================================

import { getSecret, museBase } from './config';

export type ProviderShape = 'openai' | 'anthropic' | 'gemini-openai';

export interface Provider {
  id: string;
  label: string;
  baseUrl: string;
  keyEnv: string;
  browserDirect: boolean; // CORS-reachable straight from the PWA
  shape: ProviderShape;
  modelsDevId?: string; // live public catalog fallback (https://models.dev)
  openrouterPrefix?: string; // fallback routing via OpenRouter (vendor slug)
  local?: boolean;
  curated?: string[]; // fallback models when /models is unavailable
  note?: string;
}

// The list mirrors the MUSE CLI provider picker. browserDirect=true ⇒ usable
// with no server. OAuth/IAM-only providers are listed but route via gateway.
export const PROVIDERS: Provider[] = [
  { id: 'openrouter', label: 'OpenRouter', baseUrl: 'https://openrouter.ai/api/v1', keyEnv: 'OPENROUTER_API_KEY', browserDirect: true, shape: 'openai', modelsDevId: 'openrouter', curated: ['openrouter/auto', 'anthropic/claude-opus-5', 'anthropic/claude-sonnet-5', 'openai/gpt-5.6-sol', 'moonshotai/kimi-k3', 'google/gemini-3.6-flash'], note: '400+ models — the universal fallback.' },
  { id: 'anthropic', label: 'Anthropic (Claude)', baseUrl: 'https://api.anthropic.com', keyEnv: 'ANTHROPIC_API_KEY', browserDirect: true, shape: 'anthropic', modelsDevId: 'anthropic', openrouterPrefix: 'anthropic', curated: ['claude-opus-5', 'claude-sonnet-5', 'claude-fable-5', 'claude-opus-4-8'] },
  { id: 'openai', label: 'OpenAI', baseUrl: 'https://api.openai.com/v1', keyEnv: 'OPENAI_API_KEY', browserDirect: false, shape: 'openai', modelsDevId: 'openai', openrouterPrefix: 'openai', curated: ['gpt-5.6-sol', 'gpt-5.6-terra', 'gpt-5.6-luna', 'gpt-5.6'], note: 'No browser CORS — routes via OpenRouter/gateway.' },
  { id: 'google', label: 'Google AI (Gemini)', baseUrl: 'https://generativelanguage.googleapis.com/v1beta/openai', keyEnv: 'GEMINI_API_KEY', browserDirect: true, shape: 'gemini-openai', modelsDevId: 'google', openrouterPrefix: 'google', curated: ['gemini-3.6-flash', 'gemini-3.5-flash', 'gemini-3.5-flash-lite', 'gemini-3.1-pro-preview'] },
  { id: 'groq', label: 'Groq', baseUrl: 'https://api.groq.com/openai/v1', keyEnv: 'GROQ_API_KEY', browserDirect: true, shape: 'openai', modelsDevId: 'groq', curated: ['openai/gpt-oss-120b', 'llama-3.3-70b-versatile', 'qwen/qwen3-32b'] },
  { id: 'mistral', label: 'Mistral', baseUrl: 'https://api.mistral.ai/v1', keyEnv: 'MISTRAL_API_KEY', browserDirect: true, shape: 'openai', modelsDevId: 'mistral', openrouterPrefix: 'mistralai', curated: ['mistral-medium-2604', 'mistral-small-2603', 'devstral-latest'] },
  { id: 'deepseek', label: 'DeepSeek', baseUrl: 'https://api.deepseek.com', keyEnv: 'DEEPSEEK_API_KEY', browserDirect: true, shape: 'openai', modelsDevId: 'deepseek', openrouterPrefix: 'deepseek', curated: ['deepseek-v4-pro', 'deepseek-v4-flash', 'deepseek-chat', 'deepseek-reasoner'] },
  { id: 'xai', label: 'xAI (Grok)', baseUrl: 'https://api.x.ai/v1', keyEnv: 'XAI_API_KEY', browserDirect: true, shape: 'openai', modelsDevId: 'xai', openrouterPrefix: 'x-ai', curated: ['grok-4.5', 'grok-4.3', 'grok-4.20-0309-reasoning'] },
  { id: 'together', label: 'Together AI', baseUrl: 'https://api.together.xyz/v1', keyEnv: 'TOGETHER_API_KEY', browserDirect: true, shape: 'openai', modelsDevId: 'togetherai', curated: ['nvidia/nemotron-3-ultra-550b-a55b', 'zai-org/GLM-5.2', 'Qwen/Qwen3.7-Max', 'MiniMaxAI/MiniMax-M3'] },
  { id: 'novita', label: 'NovitaAI', baseUrl: 'https://api.novita.ai/v3/openai', keyEnv: 'NOVITA_API_KEY', browserDirect: true, shape: 'openai', modelsDevId: 'novita-ai', curated: ['zai-org/glm-5.2', 'google/gemma-4-31b-it', 'moonshotai/kimi-k3'] },
  { id: 'nim', label: 'NVIDIA NIM', baseUrl: 'https://integrate.api.nvidia.com/v1', keyEnv: 'NIM_API_KEY', browserDirect: true, shape: 'openai', modelsDevId: 'nvidia', curated: ['nvidia/nemotron-3-ultra-550b-a55b', 'nvidia/nemotron-3-super-120b-a12b', 'nvidia/nemotron-3-nano-30b-a3b'] },
  { id: 'dashscope', label: 'Qwen / DashScope', baseUrl: 'https://dashscope-intl.aliyuncs.com/compatible-mode/v1', keyEnv: 'DASHSCOPE_API_KEY', browserDirect: true, shape: 'openai', modelsDevId: 'alibaba', openrouterPrefix: 'qwen', curated: ['qwen3.7-plus', 'qwen3.7-max', 'qwen3.6-plus'] },
  { id: 'moonshot', label: 'Kimi / Moonshot', baseUrl: 'https://api.moonshot.ai/v1', keyEnv: 'MOONSHOT_API_KEY', browserDirect: true, shape: 'openai', modelsDevId: 'moonshotai', curated: ['kimi-k3', 'kimi-k2.7-code', 'kimi-k2.7-code-highspeed', 'kimi-k2.6'] },
  { id: 'zhipu', label: 'Z.AI / GLM (Zhipu)', baseUrl: 'https://open.bigmodel.cn/api/paas/v4', keyEnv: 'ZHIPU_API_KEY', browserDirect: true, shape: 'openai', modelsDevId: 'zhipuai', curated: ['glm-5.2', 'glm-5.1', 'glm-5v-turbo'] },
  { id: 'stepfun', label: 'StepFun', baseUrl: 'https://api.stepfun.com/v1', keyEnv: 'STEPFUN_API_KEY', browserDirect: true, shape: 'openai', modelsDevId: 'stepfun', curated: ['step-3.7-flash', 'step-3.5-flash'] },
  { id: 'minimax', label: 'MiniMax', baseUrl: 'https://api.minimax.chat/v1', keyEnv: 'MINIMAX_API_KEY', browserDirect: true, shape: 'openai', modelsDevId: 'minimax', curated: ['MiniMax-M3', 'MiniMax-M2.7', 'MiniMax-M2.7-highspeed'] },
  { id: 'huggingface', label: 'Hugging Face', baseUrl: 'https://router.huggingface.co/v1', keyEnv: 'HF_TOKEN', browserDirect: true, shape: 'openai', modelsDevId: 'huggingface', curated: ['zai-org/GLM-5.2', 'google/gemma-4-31B-it', 'Qwen/Qwen3.5-397B-A17B'] },
  { id: 'github-models', label: 'GitHub Models', baseUrl: 'https://models.github.ai/inference', keyEnv: 'GITHUB_TOKEN', browserDirect: false, shape: 'openai', modelsDevId: 'github-models', openrouterPrefix: 'openai', curated: ['openai/gpt-4.1', 'deepseek/deepseek-r1-0528', 'mistral-ai/mistral-medium-2505', 'meta/llama-4-maverick-17b-128e-instruct-fp8'] },
  { id: 'nous', label: 'Nous Portal', baseUrl: 'https://inference-api.nousresearch.com/v1', keyEnv: 'NOUS_API_KEY', browserDirect: true, shape: 'openai', curated: ['anthropic/claude-opus-4.7', 'anthropic/claude-sonnet-4.6', 'moonshotai/kimi-k2.6', 'openai/gpt-5.5'] },
  { id: 'arcee', label: 'Arcee AI', baseUrl: 'https://conductor.arcee.ai/v1', keyEnv: 'ARCEE_API_KEY', browserDirect: true, shape: 'openai', curated: ['trinity-large-thinking', 'trinity-large-preview', 'trinity-mini'] },
  { id: 'cerebras', label: 'Cerebras', baseUrl: 'https://api.cerebras.ai/v1', keyEnv: 'CEREBRAS_API_KEY', browserDirect: true, shape: 'openai', modelsDevId: 'cerebras', curated: ['gemma-4-31b', 'zai-glm-4.7', 'gpt-oss-120b'] },
  { id: 'perplexity', label: 'Perplexity', baseUrl: 'https://api.perplexity.ai', keyEnv: 'PERPLEXITY_API_KEY', browserDirect: true, shape: 'openai', modelsDevId: 'perplexity', curated: ['sonar-deep-research', 'sonar-pro', 'sonar'] },
  { id: 'fireworks', label: 'Fireworks', baseUrl: 'https://api.fireworks.ai/inference/v1', keyEnv: 'FIREWORKS_API_KEY', browserDirect: true, shape: 'openai', modelsDevId: 'fireworks-ai', curated: ['accounts/fireworks/routers/kimi-k3-fast', 'accounts/fireworks/models/kimi-k3', 'accounts/fireworks/routers/glm-5p2-fast'] },
  { id: 'azure', label: 'Azure OpenAI', baseUrl: '', keyEnv: 'AZURE_OPENAI_API_KEY', browserDirect: false, shape: 'openai', note: 'Per-deployment endpoint — configure via gateway.' },
  { id: 'bedrock', label: 'AWS Bedrock', baseUrl: '', keyEnv: 'AWS_BEDROCK', browserDirect: false, shape: 'openai', note: 'IAM-signed — gateway only.' },
  { id: 'vercel', label: 'Vercel AI Gateway', baseUrl: 'https://ai-gateway.vercel.sh/v1', keyEnv: 'AI_GATEWAY_API_KEY', browserDirect: true, shape: 'openai', modelsDevId: 'vercel', curated: ['anthropic/claude-opus-5', 'openai/gpt-5.6-sol', 'moonshotai/kimi-k3', 'google/gemini-3.6-flash'] },
  { id: 'lmstudio', label: 'LM Studio (local)', baseUrl: 'http://localhost:1234/v1', keyEnv: 'LMSTUDIO_API_KEY', browserDirect: true, shape: 'openai', local: true, curated: ['local-model'], note: 'Enable the local server in LM Studio.' },
  { id: 'ollama', label: 'Ollama (local)', baseUrl: 'http://localhost:11434/v1', keyEnv: 'OLLAMA_API_KEY', browserDirect: true, shape: 'openai', local: true, curated: ['llama3.2', 'qwen2.5-coder'], note: 'Set OLLAMA_ORIGINS to allow the browser.' },
  { id: 'ollama-cloud', label: 'Ollama Cloud', baseUrl: 'https://ollama.com/v1', keyEnv: 'OLLAMA_API_KEY', browserDirect: false, shape: 'openai', modelsDevId: 'ollama-cloud', curated: ['kimi-k3', 'glm-5.2', 'gemma4:31b', 'qwen3.5:397b', 'minimax-m3', 'kimi-k2.7-code', 'deepseek-v4-pro'], note: 'Hosted Ollama models with your ollama.com key; requests route through the gateway because ollama.com does not allow browser CORS.' },
  { id: 'alibaba-coding-plan', label: 'Alibaba Coding Plan (Qwen)', baseUrl: 'https://coding-intl.dashscope.aliyuncs.com/v1', keyEnv: 'ALIBABA_CODING_PLAN_API_KEY', browserDirect: true, shape: 'openai', modelsDevId: 'alibaba', curated: ['qwen3.7-plus', 'qwen3.7-max', 'qwen3.6-plus'] },
  { id: 'gmi', label: 'GMI Cloud', baseUrl: 'https://api.gmi-serving.com/v1', keyEnv: 'GMI_API_KEY', browserDirect: true, shape: 'openai', modelsDevId: 'gmicloud', curated: ['zai-org/GLM-5.2-FP8', 'moonshotai/kimi-k2.7-code-highspeed', 'anthropic/claude-opus-4.8'] },
  { id: 'kilocode', label: 'Kilo Code', baseUrl: 'https://api.kilo.ai/api/gateway', keyEnv: 'KILOCODE_API_KEY', browserDirect: true, shape: 'openai', modelsDevId: 'kilo', curated: ['minimax/minimax-m3', 'google/gemini-3.5-flash', 'qwen/qwen3.7-max'], note: 'Routing gateway over many coding models.' },
  { id: 'opencode-zen', label: 'OpenCode Zen', baseUrl: 'https://opencode.ai/zen/v1', keyEnv: 'OPENCODE_ZEN_API_KEY', browserDirect: true, shape: 'openai', modelsDevId: 'opencode', curated: ['claude-opus-5', 'kimi-k3', 'gpt-5.6-sol', 'gemini-3.6-flash'] },
  { id: 'xiaomi', label: 'Xiaomi MiMo', baseUrl: 'https://api.xiaomimimo.com/v1', keyEnv: 'XIAOMI_API_KEY', browserDirect: true, shape: 'openai', modelsDevId: 'xiaomi', curated: ['mimo-v2.5-pro-ultraspeed', 'mimo-v2.5-pro', 'mimo-v2.5', 'mimo-v2-omni'] },
  { id: 'azure-foundry', label: 'Azure AI Foundry', baseUrl: '', keyEnv: 'AZURE_FOUNDRY_API_KEY', browserDirect: false, shape: 'openai', note: 'Per-resource endpoint — configure via gateway.' },
  { id: 'copilot', label: 'GitHub Copilot', baseUrl: 'https://api.githubcopilot.com', keyEnv: 'COPILOT_GITHUB_TOKEN', browserDirect: false, shape: 'openai', modelsDevId: 'github-copilot', curated: ['gpt-5.5', 'claude-opus-4.8', 'claude-sonnet-4.6', 'gemini-3.1-pro-preview'], note: 'GitHub token — routes via gateway.' },
  { id: 'openai-codex', label: 'OpenAI Codex (OAuth)', baseUrl: '', keyEnv: 'OPENAI_CODEX_TOKEN', browserDirect: false, shape: 'openai', curated: ['gpt-5-codex'], note: 'OAuth/ChatGPT sign-in — gateway only.' },
  { id: 'qwen-oauth', label: 'Qwen (OAuth)', baseUrl: '', keyEnv: 'QWEN_OAUTH_TOKEN', browserDirect: false, shape: 'openai', curated: ['qwen3-coder-plus'], note: 'Browser device-code sign-in — gateway only.' },
  { id: 'copilot-acp', label: 'Copilot ACP', baseUrl: '', keyEnv: 'COPILOT_ACP_TOKEN', browserDirect: false, shape: 'openai', note: 'Autonomous coding process — gateway only.' },
  { id: 'custom', label: 'Custom (OpenAI-compatible)', baseUrl: '', keyEnv: 'CUSTOM_API_KEY', browserDirect: true, shape: 'openai', note: 'Add your own base URL + key in Add-ons.' },
];

const BY_ID = Object.fromEntries(PROVIDERS.map((p) => [p.id, p]));

export function getProvider(id: string): Provider | undefined {
  return BY_ID[id];
}

/** Resolve which provider a model id belongs to. Honors `providerId/model`. */
export function providerForModel(model: string): Provider {
  if (model.includes('/')) {
    const head = model.split('/')[0];
    if (BY_ID[head]) return BY_ID[head];
    // vendor slugs (anthropic/, openai/, google/) → OpenRouter
    return BY_ID.openrouter;
  }
  if (model.startsWith('claude')) return BY_ID.anthropic;
  if (model.startsWith('gpt') || model.startsWith('o1') || model.startsWith('o3') || model.startsWith('o4')) return BY_ID.openai;
  if (model.startsWith('gemini')) return BY_ID.google;
  if (model.startsWith('grok')) return BY_ID.xai;
  if (model.startsWith('deepseek')) return BY_ID.deepseek;
  if (model.startsWith('mistral') || model.startsWith('codestral')) return BY_ID.mistral;
  if (model.startsWith('glm')) return BY_ID.zhipu;
  return BY_ID.openrouter;
}

/** Has the user entered a key for this provider? (custom needs a base URL too.) */
export function isConfigured(p: Provider): boolean {
  if (p.local) return true; // local servers need no key
  const hasKey = !!getSecret(p.keyEnv);
  if (p.id === 'custom') return hasKey && !!getSecret('CUSTOM_BASE_URL');
  return hasKey;
}

export function configuredProviders(): Provider[] {
  return PROVIDERS.filter((p) => isConfigured(p) || (p.local && false));
}

export type Transport = { kind: 'direct'; provider: Provider; baseUrl: string; model: string } | { kind: 'openrouter'; provider: Provider; baseUrl: string; model: string } | { kind: 'gateway'; provider: Provider; model: string } | { kind: 'unavailable'; provider: Provider; reason: string };

/**
 * Auto-route a model to the next best available transport:
 *   provider-direct (key + browserDirect) → OpenRouter (key + prefix) →
 *   gateway (configured) → unavailable.
 */
/**
 * The vendor-neutral "no main provider" choice. MUSE/NEXUS is provider-agnostic:
 * there is deliberately NO privileged default vendor (and OpenAI is never the
 * default). `'auto'` resolves to the best model the owner can actually use right
 * now — the OpenRouter auto-router when present (it spans 300+ models across every
 * vendor), otherwise the first provider they hold a key for in list order, then a
 * configured local server. Selection is purely "what you have", with no bias.
 */
export function bestAvailableModel(): string {
  if (getSecret('OPENROUTER_API_KEY')) return 'openrouter/auto';
  for (const p of PROVIDERS) {
    if (p.local || p.id === 'custom' || p.id === 'openrouter') continue;
    if (!p.browserDirect) continue; // OAuth/IAM/gateway-only can't serve a browser pick
    const key = getSecret(p.keyEnv);
    if (key) {
      const m = p.curated?.[0];
      if (m) return m.includes('/') ? m : `${p.id}/${m}`;
    }
  }
  for (const p of PROVIDERS) {
    if (p.local && getSecret(p.keyEnv)) {
      const m = p.curated?.[0];
      if (m) return `${p.id}/${m}`;
    }
  }
  return 'openrouter/auto';
}

export function resolveModelTransport(model: string): Transport {
  if (model === 'auto') model = bestAvailableModel();
  const p = providerForModel(model);
  const baseUrl = p.id === 'custom' ? getSecret('CUSTOM_BASE_URL') : p.baseUrl;

  if (p.browserDirect && baseUrl && isConfigured(p)) {
    return { kind: 'direct', provider: p, baseUrl, model };
  }
  // Fallback 1: OpenRouter, if a key exists and the model has an OR vendor slug.
  const orKey = getSecret('OPENROUTER_API_KEY');
  if (orKey && (p.id === 'openrouter' || p.openrouterPrefix)) {
    const orModel = p.id === 'openrouter' ? model.replace(/^openrouter\//, '') : `${p.openrouterPrefix}/${model.split('/').pop()}`;
    return { kind: 'openrouter', provider: getProvider('openrouter')!, baseUrl: getProvider('openrouter')!.baseUrl, model: orModel };
  }
  // Fallback 2: the local MUSE gateway.
  if (museBase()) return { kind: 'gateway', provider: p, model };
  return { kind: 'unavailable', provider: p, reason: p.browserDirect ? `add a ${p.label} key in Settings` : 'add an OpenRouter key or start the gateway' };
}
