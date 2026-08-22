import { PassThrough } from 'stream'

import { renderSync } from '@hermes/ink'
import React from 'react'
import { describe, expect, it, vi } from 'vitest'

const inputHarness = vi.hoisted(() => ({
  /** Live keyboard handlers, keyed by the hook instance that owns them. */
  handlers: new Map<object, (input: string, key: Record<string, boolean>) => void>()
}))

/**
 * Stub `useInput` so the panel doesn't try to enter raw mode under renderSync
 * (PassThrough stdin doesn't support it). Box/Text pass through to real Ink.
 *
 * Keyed by a per-hook `useRef` slot rather than appended to a list: RoomsPanel
 * calls `useInput` twice on EVERY render (useOverlayKeys' close keys, then its
 * own navigation keys), so a plain array would grow one stale copy of each per
 * frame and a single keypress would be delivered a dozen times. The slot makes
 * a re-render replace its handler, and the effect cleanup drops it on unmount.
 */
vi.mock('@hermes/ink', async importOriginal => {
  const mod = await importOriginal()

  return {
    ...mod,
    useInput: (handler: (input: string, key: Record<string, boolean>) => void) => {
      const slot = React.useRef({}).current

      inputHarness.handlers.set(slot, handler)

      React.useEffect(
        () => () => {
          inputHarness.handlers.delete(slot)
        },
        [slot]
      )
    }
  }
})

import { RoomsPanel } from '../components/roomsPanel.js'
import type { GatewayClient } from '../gatewayClient.js'
import { stripAnsi } from '../lib/text.js'
import { DEFAULT_THEME } from '../theme.js'

const t = DEFAULT_THEME

const NO_KEY: Record<string, boolean> = {}

const flush = () => new Promise(resolve => setImmediate(resolve))

interface StubCall {
  method: string
  params: Record<string, unknown>
}

/**
 * Mount a RoomsPanel over a stub gateway.
 *
 * `press` fans a keystroke out to every live handler. That is only correct
 * while no TextInput is mounted — i.e. on the list and confirm screens — so
 * the tests below never type into the editor. The editor itself is driven by
 * real bytes on a real hermes-ink input pipeline in `roomsPanelEditor.test.tsx`
 * (focus-aware, so the two TextInputs behave), and the RPC contract behind
 * create/update is covered by tests/tui_gateway/test_methods_rooms.py.
 */
function mount(responses: Record<string, unknown>, failing: string[] = []) {
  const stdout = new PassThrough()
  const stdin = new PassThrough()
  const stderr = new PassThrough()
  const calls: StubCall[] = []

  let output = ''

  Object.assign(stdout, { columns: 100, isTTY: false, rows: 40 })
  Object.assign(stdin, { isTTY: false })
  Object.assign(stderr, { isTTY: false })
  stdout.on('data', chunk => {
    output += chunk.toString()
  })

  const gw = {
    request: (method: string, params: Record<string, unknown>) => {
      calls.push({ method, params })

      if (failing.includes(method)) {
        return Promise.reject(new Error(`${method} exploded`))
      }

      return Promise.resolve(responses[method] ?? {})
    }
  } as unknown as GatewayClient

  inputHarness.handlers.clear()

  const instance = renderSync(React.createElement(RoomsPanel, { gw, onClose: () => {}, t }), {
    patchConsole: false,
    stderr: stderr as NodeJS.WriteStream,
    stdin: stdin as NodeJS.ReadStream,
    stdout: stdout as NodeJS.WriteStream
  })

  return {
    calls,
    cleanup: () => {
      instance.unmount()
      instance.cleanup()
    },
    /** Drop everything painted so far, so the next `frame()` is only new. */
    clear: () => {
      output = ''
    },
    frame: () => stripAnsi(output),
    press: (ch: string, key: Record<string, boolean> = NO_KEY) => {
      for (const handler of [...inputHarness.handlers.values()]) {
        handler(ch, key)
      }
    }
  }
}

const ROOMS = [
  { id: 'room_1', memberIds: ['scout', 'smith'], name: 'Launch Crew' },
  { id: 'room_2', memberIds: [], name: 'Empty Board' }
]

describe('RoomsPanel', () => {
  it('lists what rooms.list returned, with member counts and the roster', async () => {
    const panel = mount({ 'rooms.list': { rooms: ROOMS } })

    await flush()
    const frame = panel.frame()

    expect(panel.calls[0]).toEqual({ method: 'rooms.list', params: {} })
    expect(frame).toContain('Launch Crew')
    expect(frame).toContain('2 members')
    expect(frame).toContain('Empty Board')
    // Singular/plural, and the selected room's roster spelled out below.
    expect(frame).toContain('0 members')
    expect(frame).toContain('scout, smith')

    panel.cleanup()
  })

  it('says so, and how to fix it, when the store is empty', async () => {
    // The whole point of the write path: a first run has nothing, and the
    // empty state has to carry the way out of it.
    const panel = mount({ 'rooms.list': { rooms: [] } })

    await flush()
    const frame = panel.frame()

    expect(frame).toContain('No rooms yet.')
    expect(frame).toContain('n new room')

    panel.cleanup()
  })

  it('does not claim "no rooms yet" when the list actually failed', async () => {
    const panel = mount({}, ['rooms.list'])

    await flush()
    const frame = panel.frame()

    expect(frame).toContain('rooms.list exploded')
    expect(frame).not.toContain('No rooms yet.')

    panel.cleanup()
  })

  it('opens an empty form on n', async () => {
    const panel = mount({ 'rooms.list': { rooms: ROOMS } })

    await flush()
    panel.clear()
    panel.press('n')
    await flush()

    const frame = panel.frame()

    expect(frame).toContain('New room')
    expect(frame).toContain('name')
    expect(frame).toContain('members')
    // A new room starts blank, not on top of whatever was selected.
    expect(frame).not.toContain('Launch Crew')

    panel.cleanup()
  })

  it('opens the selected room prefilled on e', async () => {
    const panel = mount({ 'rooms.list': { rooms: ROOMS } })

    await flush()
    panel.clear()
    panel.press('e')
    await flush()

    const frame = panel.frame()

    expect(frame).toContain('Edit room')
    expect(frame).toContain('Launch Crew')
    // The roster arrives in the comma-separated spelling the field parses.
    expect(frame).toContain('scout, smith')

    panel.cleanup()
  })

  it('confirms before deleting, and only deletes on y', async () => {
    const panel = mount({
      'rooms.delete': { deleted: true },
      'rooms.list': { rooms: ROOMS }
    })

    await flush()
    panel.clear()
    panel.press('d')
    await flush()

    expect(panel.frame()).toContain('Delete')
    // Nothing has been sent yet — the confirm screen is not a delete.
    expect(panel.calls.map(c => c.method)).toEqual(['rooms.list'])

    panel.press('n')
    await flush()
    expect(panel.calls.map(c => c.method)).toEqual(['rooms.list'])

    panel.press('d')
    await flush()
    panel.press('y')
    await flush()

    expect(panel.calls[1]).toEqual({ method: 'rooms.delete', params: { id: 'room_1' } })
    // ...and the list is re-read, so ordering comes from the store.
    expect(panel.calls.map(c => c.method)).toEqual(['rooms.list', 'rooms.delete', 'rooms.list'])

    panel.cleanup()
  })

  it('deletes the room the cursor is on, not always the first', async () => {
    const panel = mount({
      'rooms.delete': { deleted: true },
      'rooms.list': { rooms: ROOMS }
    })

    await flush()
    panel.press('j')
    await flush()
    panel.press('d')
    await flush()
    panel.press('y')
    await flush()

    expect(panel.calls[1]).toEqual({ method: 'rooms.delete', params: { id: 'room_2' } })

    panel.cleanup()
  })

  it('re-reads the list on r', async () => {
    const panel = mount({ 'rooms.list': { rooms: ROOMS } })

    await flush()
    panel.press('r')
    await flush()

    expect(panel.calls.map(c => c.method)).toEqual(['rooms.list', 'rooms.list'])

    panel.cleanup()
  })
})
