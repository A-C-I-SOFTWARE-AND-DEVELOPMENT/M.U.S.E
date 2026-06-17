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
  openrouterPrefix?: string; // fallback routing via OpenRouter (vendor slug)
  local?: boolean;
  curated?: string[]; // fallback models when /models is unavailable
  note?: string;
}

// The list mirrors the MUSE CLI provider picker. browserDirect=true ⇒ usable
// with no server. OAuth/IAM-only providers are listed but route via gateway.
export const PROVIDERS: Provider[] = [
  { id: 'openrouter', label: 'OpenRouter', baseUrl: 'https://openrouter.ai/api/v1', keyEnv: 'OPENROUTER_API_KEY', browserDirect: true, shape: 'openai', curated: ['openrouter/auto', 'anthropic/claude-3.7-sonnet', 'openai/gpt-4o', 'google/gemini-2.0-flash-001', 'meta-llama/llama-3.3-70b-instruct', 'deepseek/deepseek-chat'], note: '300+ models — the universal fallback.' },
  { id: 'anthropic', label: 'Anthropic (Claude)', baseUrl: 'https://api.anthropic.com', keyEnv: 'ANTHROPIC_API_KEY', browserDirect: true, shape: 'anthropic', openrouterPrefix: 'anthropic', curated: ['claude-3-7-sonnet-latest', 'claude-3-5-haiku-latest'] },
  { id: 'openai', label: 'OpenAI', baseUrl: 'https://api.openai.com/v1', keyEnv: 'OPENAI_API_KEY', browserDirect: false, shape: 'openai', openrouterPrefix: 'openai', curated: ['gpt-4o', 'gpt-4o-mini', 'o3-mini'], note: 'No browser CORS — routes via OpenRouter/gateway.' },
  { id: 'google', label: 'Google AI (Gemini)', baseUrl: 'https://generativelanguage.googleapis.com/v1beta/openai', keyEnv: 'GEMINI_API_KEY', browserDirect: true, shape: 'gemini-openai', openrouterPrefix: 'google', curated: ['gemini-2.0-flash', 'gemini-1.5-pro'] },
  { id: 'groq', label: 'Groq', baseUrl: 'https://api.groq.com/openai/v1', keyEnv: 'GROQ_API_KEY', browserDirect: true, shape: 'openai', curated: ['llama-3.3-70b-versatile', 'llama-3.1-8b-instant', 'qwen-2.5-coder-32b'] },
  { id: 'mistral', label: 'Mistral', baseUrl: 'https://api.mistral.ai/v1', keyEnv: 'MISTRAL_API_KEY', browserDirect: true, shape: 'openai', openrouterPrefix: 'mistralai', curated: ['mistral-large-latest', 'codestral-latest'] },
  { id: 'deepseek', label: 'DeepSeek', baseUrl: 'https://api.deepseek.com', keyEnv: 'DEEPSEEK_API_KEY', browserDirect: true, shape: 'openai', openrouterPrefix: 'deepseek', curated: ['deepseek-chat', 'deepseek-reasoner'] },
  { id: 'xai', label: 'xAI (Grok)', baseUrl: 'https://api.x.ai/v1', keyEnv: 'XAI_API_KEY', browserDirect: true, shape: 'openai', openrouterPrefix: 'x-ai', curated: ['grok-2-latest', 'grok-beta'] },
  { id: 'together', label: 'Together AI', baseUrl: 'https://api.together.xyz/v1', keyEnv: 'TOGETHER_API_KEY', browserDirect: true, shape: 'openai', curated: ['meta-llama/Llama-3.3-70B-Instruct-Turbo', 'Qwen/Qwen2.5-Coder-32B-Instruct'] },
  { id: 'novita', label: 'NovitaAI', baseUrl: 'https://api.novita.ai/v3/openai', keyEnv: 'NOVITA_API_KEY', browserDirect: true, shape: 'openai', curated: ['meta-llama/llama-3.3-70b-instruct'] },
  { id: 'nim', label: 'NVIDIA NIM', baseUrl: 'https://integrate.api.nvidia.com/v1', keyEnv: 'NIM_API_KEY', browserDirect: true, shape: 'openai', curated: ['meta/llama-3.3-70b-instruct', 'nvidia/nemotron-4-340b-instruct'] },
  { id: 'dashscope', label: 'Qwen / DashScope', baseUrl: 'https://dashscope-intl.aliyuncs.com/compatible-mode/v1', keyEnv: 'DASHSCOPE_API_KEY', browserDirect: true, shape: 'openai', openrouterPrefix: 'qwen', curated: ['qwen-max', 'qwen2.5-coder-32b-instruct'] },
  { id: 'moonshot', label: 'Kimi / Moonshot', baseUrl: 'https://api.moonshot.ai/v1', keyEnv: 'MOONSHOT_API_KEY', browserDirect: true, shape: 'openai', curated: ['moonshot-v1-128k', 'kimi-latest'] },
  { id: 'zhipu', label: 'Z.AI / GLM (Zhipu)', baseUrl: 'https://open.bigmodel.cn/api/paas/v4', keyEnv: 'ZHIPU_API_KEY', browserDirect: true, shape: 'openai', curated: ['glm-4-plus', 'glm-4-flash'] },
  { id: 'stepfun', label: 'StepFun', baseUrl: 'https://api.stepfun.com/v1', keyEnv: 'STEPFUN_API_KEY', browserDirect: true, shape: 'openai', curated: ['step-2-16k'] },
  { id: 'minimax', label: 'MiniMax', baseUrl: 'https://api.minimax.chat/v1', keyEnv: 'MINIMAX_API_KEY', browserDirect: true, shape: 'openai', curated: ['abab6.5s-chat'] },
  { id: 'huggingface', label: 'Hugging Face', baseUrl: 'https://router.huggingface.co/v1', keyEnv: 'HF_TOKEN', browserDirect: true, shape: 'openai', curated: ['meta-llama/Llama-3.3-70B-Instruct'] },
  { id: 'github-models', label: 'GitHub Models', baseUrl: 'https://models.inference.ai.azure.com', keyEnv: 'GITHUB_TOKEN', browserDirect: false, shape: 'openai', openrouterPrefix: 'openai', curated: ['gpt-4o', 'Llama-3.3-70B-Instruct'] },
  { id: 'nous', label: 'Nous Portal', baseUrl: 'https://inference-api.nousresearch.com/v1', keyEnv: 'NOUS_API_KEY', browserDirect: true, shape: 'openai', curated: ['Hermes-3-Llama-3.1-70B'] },
  { id: 'arcee', label: 'Arcee AI', baseUrl: 'https://conductor.arcee.ai/v1', keyEnv: 'ARCEE_API_KEY', browserDirect: true, shape: 'openai', curated: ['auto'] },
  { id: 'cerebras', label: 'Cerebras', baseUrl: 'https://api.cerebras.ai/v1', keyEnv: 'CEREBRAS_API_KEY', browserDirect: true, shape: 'openai', curated: ['llama-3.3-70b'] },
  { id: 'perplexity', label: 'Perplexity', baseUrl: 'https://api.perplexity.ai', keyEnv: 'PERPLEXITY_API_KEY', browserDirect: true, shape: 'openai', curated: ['sonar', 'sonar-pro'] },
  { id: 'fireworks', label: 'Fireworks', baseUrl: 'https://api.fireworks.ai/inference/v1', keyEnv: 'FIREWORKS_API_KEY', browserDirect: true, shape: 'openai', curated: ['accounts/fireworks/models/llama-v3p3-70b-instruct'] },
  { id: 'azure', label: 'Azure OpenAI', baseUrl: '', keyEnv: 'AZURE_OPENAI_API_KEY', browserDirect: false, shape: 'openai', note: 'Per-deployment endpoint — configure via gateway.' },
  { id: 'bedrock', label: 'AWS Bedrock', baseUrl: '', keyEnv: 'AWS_BEDROCK', browserDirect: false, shape: 'openai', note: 'IAM-signed — gateway only.' },
  { id: 'vercel', label: 'Vercel AI Gateway', baseUrl: 'https://ai-gateway.vercel.sh/v1', keyEnv: 'AI_GATEWAY_API_KEY', browserDirect: true, shape: 'openai', curated: ['anthropic/claude-3.7-sonnet', 'openai/gpt-4o'] },
  { id: 'lmstudio', label: 'LM Studio (local)', baseUrl: 'http://localhost:1234/v1', keyEnv: 'LMSTUDIO_API_KEY', browserDirect: true, shape: 'openai', local: true, curated: ['local-model'], note: 'Enable the local server in LM Studio.' },
  { id: 'ollama', label: 'Ollama (local)', baseUrl: 'http://localhost:11434/v1', keyEnv: 'OLLAMA_API_KEY', browserDirect: true, shape: 'openai', local: true, curated: ['llama3.2', 'qwen2.5-coder'], note: 'Set OLLAMA_ORIGINS to allow the browser.' },
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

export type Transport =
  | { kind: 'direct'; provider: Provider; baseUrl: string; model: string }
  | { kind: 'openrouter'; provider: Provider; baseUrl: string; model: string }
  | { kind: 'gateway'; provider: Provider; model: string }
  | { kind: 'unavailable'; provider: Provider; reason: string };

/**
 * Auto-route a model to the next best available transport:
 *   provider-direct (key + browserDirect) → OpenRouter (key + prefix) →
 *   gateway (configured) → unavailable.
 */
export function resolveModelTransport(model: string): Transport {
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
