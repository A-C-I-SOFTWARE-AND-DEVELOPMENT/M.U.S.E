import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { localGatewayBlockedByHttps } from '../src/lib/connect';
import { resetConfig, setConfig } from '../src/lib/config';

// jsdom lets us override location.protocol per test.
function setProtocol(p: string) {
  Object.defineProperty(window, 'location', {
    value: { ...window.location, protocol: p },
    writable: true,
    configurable: true,
  });
}

describe('localGatewayBlockedByHttps', () => {
  beforeEach(() => resetConfig());
  afterEach(() => setProtocol('http:'));

  it('is true when an HTTPS page targets a local http gateway (mixed content)', () => {
    setProtocol('https:');
    expect(localGatewayBlockedByHttps('http://127.0.0.1:8765')).toBe(true);
    expect(localGatewayBlockedByHttps('http://localhost:8765')).toBe(true);
    expect(localGatewayBlockedByHttps('http://192.168.1.20:8765')).toBe(true);
  });

  it('is false for an https gateway (no mixed content)', () => {
    setProtocol('https:');
    expect(localGatewayBlockedByHttps('https://gw.example.com')).toBe(false);
  });

  it('is false when the page itself is http (e.g. local dev)', () => {
    setProtocol('http:');
    expect(localGatewayBlockedByHttps('http://127.0.0.1:8765')).toBe(false);
  });

  it('falls back to the configured gateway when no arg is given', () => {
    setProtocol('https:');
    setConfig({ museBaseUrl: 'http://localhost:8765' });
    expect(localGatewayBlockedByHttps()).toBe(true);
  });

  it('is false for a public http host that is not local/private', () => {
    setProtocol('https:');
    expect(localGatewayBlockedByHttps('http://example.com:8765')).toBe(false);
  });
});
