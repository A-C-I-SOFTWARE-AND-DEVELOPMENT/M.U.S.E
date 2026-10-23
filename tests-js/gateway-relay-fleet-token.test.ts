/**
 * The hosted relay's fleet token must only ever reach the fleet origin.
 *
 * MUSE_GATEWAY_RELAY_TOKEN unlocks Caddy for every hosted cockpit, while an
 * account's gateway URL is user-chosen. If the relay attached the token to any
 * bound host, one signup pointing at an attacker server would leak it.
 */
import { describe, expect, it } from 'vitest'

import { isFleetTarget } from '../api/gateway/[...path]'

const FLEET = 'https://gw.musehq.io'

describe('isFleetTarget', () => {
  it('matches only the exact fleet origin', () => {
    expect(isFleetTarget('https://gw.musehq.io/u/alice/v1/health', FLEET)).toBe(true)
    expect(isFleetTarget('https://attacker.example/v1/health', FLEET)).toBe(false)
    expect(isFleetTarget('https://gw.musehq.io.attacker.example/v1/health', FLEET)).toBe(false)
    expect(isFleetTarget('https://gw.musehq.io:8443/v1/health', FLEET)).toBe(false)
    expect(isFleetTarget('http://gw.musehq.io/v1/health', FLEET)).toBe(false)
  })

  it('fails closed when the fleet origin is unset or invalid', () => {
    expect(isFleetTarget('https://gw.musehq.io/v1/health', '')).toBe(false)
    expect(isFleetTarget('https://gw.musehq.io/v1/health', 'not a url')).toBe(false)
    expect(isFleetTarget('https://gw.musehq.io/v1/health', 'http://gw.musehq.io')).toBe(false)
    expect(isFleetTarget('garbage', FLEET)).toBe(false)
  })
})
