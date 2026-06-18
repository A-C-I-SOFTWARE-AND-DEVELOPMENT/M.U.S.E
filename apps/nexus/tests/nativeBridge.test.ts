import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  clearNativeToken,
  engageEmergencyStop,
  isNativeShell,
  nativeToken,
  setNativeToken,
  shellInfo,
  voiceStart,
} from '../src/lib/nativeBridge';

afterEach(() => {
  delete (window as unknown as { NexusBridge?: unknown }).NexusBridge;
  vi.restoreAllMocks();
});

function installBridge(overrides: Record<string, unknown> = {}) {
  const base = {
    shellInfo: () =>
      JSON.stringify({
        shell: 'android',
        bridgeVersion: 1,
        appVersion: '2026.06.18',
        trustedOrigin: true,
        capabilities: ['token', 'voice', 'overlay', 'emergencyStop'],
      }),
    getToken: () => 'tok_abc',
    setToken: () => true,
    clearToken: () => true,
    voiceStart: () => true,
    voiceStop: () => true,
    overlayShow: () => true,
    overlayHide: () => true,
    engageEmergencyStop: () => true,
  };
  (window as unknown as { NexusBridge: unknown }).NexusBridge = { ...base, ...overrides };
}

describe('nativeBridge — plain browser (no shell)', () => {
  it('reports not-in-shell and degrades every helper to a safe default', () => {
    expect(isNativeShell()).toBe(false);
    expect(shellInfo()).toBeNull();
    expect(nativeToken()).toBeNull();
    expect(setNativeToken('x')).toBe(false);
    expect(clearNativeToken()).toBe(false);
    expect(voiceStart()).toBe(false);
    expect(engageEmergencyStop()).toBe(false);
  });
});

describe('nativeBridge — inside the native shell', () => {
  it('detects the shell and parses shellInfo', () => {
    installBridge();
    expect(isNativeShell()).toBe(true);
    const info = shellInfo();
    expect(info?.bridgeVersion).toBe(1);
    expect(info?.capabilities).toContain('emergencyStop');
  });

  it('passes the token through, and treats an empty token as unpaired (null)', () => {
    installBridge();
    expect(nativeToken()).toBe('tok_abc');
    installBridge({ getToken: () => '' });
    expect(nativeToken()).toBeNull();
  });

  it('returns null shellInfo on a malformed native reply', () => {
    installBridge({ shellInfo: () => 'not-json' });
    expect(shellInfo()).toBeNull();
  });

  it('forwards control calls to the bridge', () => {
    const engage = vi.fn(() => true);
    installBridge({ engageEmergencyStop: engage });
    expect(engageEmergencyStop()).toBe(true);
    expect(engage).toHaveBeenCalledOnce();
  });
});
