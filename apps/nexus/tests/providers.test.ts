import { describe, it, expect, beforeEach } from 'vitest';
import { providerForModel, resolveModelTransport, isConfigured, getProvider } from '../src/lib/providers';
import { setSecret, setConfig, resetConfig } from '../src/lib/config';

beforeEach(() => {
  resetConfig();
});

describe('providerForModel', () => {
  it('routes by known model prefixes', () => {
    expect(providerForModel('claude-3-7-sonnet').id).toBe('anthropic');
    expect(providerForModel('gpt-4o').id).toBe('openai');
    expect(providerForModel('gemini-2.0-flash').id).toBe('google');
    expect(providerForModel('grok-2-latest').id).toBe('xai');
    expect(providerForModel('deepseek-chat').id).toBe('deepseek');
  });
  it('honors a providerId/model prefix', () => {
    expect(providerForModel('groq/llama-3.3-70b-versatile').id).toBe('groq');
  });
  it('falls back to openrouter for unknown ids; known id prefixes win', () => {
    expect(providerForModel('some-weird-model').id).toBe('openrouter');
    expect(providerForModel('vendor-x/some-model').id).toBe('openrouter'); // unknown vendor slug → OR
    expect(providerForModel('anthropic/claude-3.7-sonnet').id).toBe('anthropic'); // 'anthropic' is a known provider id
  });
});

describe('isConfigured', () => {
  it('true once the provider key is set; local providers always true', () => {
    expect(isConfigured(getProvider('anthropic')!)).toBe(false);
    setSecret('ANTHROPIC_API_KEY', 'sk-ant-x');
    expect(isConfigured(getProvider('anthropic')!)).toBe(true);
    expect(isConfigured(getProvider('ollama')!)).toBe(true); // local
  });
});

describe('resolveModelTransport — auto-route to next best', () => {
  it('uses provider-direct when a browser-direct provider has a key', () => {
    setSecret('ANTHROPIC_API_KEY', 'sk-ant-x');
    const t = resolveModelTransport('claude-3-7-sonnet');
    expect(t.kind).toBe('direct');
    expect(t.kind === 'direct' && t.provider.id).toBe('anthropic');
  });

  it('routes a non-CORS provider (OpenAI) via OpenRouter when that key exists', () => {
    setSecret('OPENROUTER_API_KEY', 'sk-or-x');
    const t = resolveModelTransport('gpt-4o');
    expect(t.kind).toBe('openrouter');
    expect(t.kind === 'openrouter' && t.model).toBe('openai/gpt-4o');
  });

  it('falls back to the gateway when no usable key but a gateway is set', () => {
    setConfig({ museBaseUrl: 'http://127.0.0.1:8765' });
    const t = resolveModelTransport('gpt-4o');
    expect(t.kind).toBe('gateway');
  });

  it('is unavailable with no keys and no gateway', () => {
    const t = resolveModelTransport('gpt-4o');
    expect(t.kind).toBe('unavailable');
  });

  it('a direct provider without its own key still routes via OpenRouter (prefix)', () => {
    setSecret('OPENROUTER_API_KEY', 'sk-or-x');
    const t = resolveModelTransport('deepseek-chat');
    expect(t.kind).toBe('openrouter');
    expect(t.kind === 'openrouter' && t.model).toBe('deepseek/deepseek-chat');
  });
});
