import { describe, it, expect } from 'vitest';
import { resolveLinkState } from '../src/lib/health';

describe('resolveLinkState — auto go online when the gateway is not established', () => {
  it('is offline only when there is no network at all', () => {
    expect(resolveLinkState(false, false, false)).toBe('offline');
    expect(resolveLinkState(true, true, false)).toBe('offline'); // gateway ok but no internet
  });

  it('is gateway when a gateway is established and reachable', () => {
    expect(resolveLinkState(true, true, true)).toBe('gateway');
  });

  it('auto-goes online when no gateway is configured but the internet is up', () => {
    expect(resolveLinkState(false, false, true)).toBe('online');
  });

  it('auto-goes online when a gateway is configured but unreachable (not offline)', () => {
    expect(resolveLinkState(true, false, true)).toBe('online');
  });
});
