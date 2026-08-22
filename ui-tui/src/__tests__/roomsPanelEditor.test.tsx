import { EventEmitter } from 'node:events'
import { PassThrough } from 'node:stream'

import { renderSync } from '@hermes/ink'
import React from 'react'
import { describe, expect, it, vi } from 'vitest'

import { RoomsPanel } from '../components/roomsPanel.js'
import type { GatewayClient } from '../gatewayClient.js'
import { DEFAULT_THEME } from '../theme.js'

/**
 * The Rooms WRITE path, driven by real bytes on stdin.
 *
 * `roomsPanel.test.tsx` stubs `useInput`, which is why it can only exercise the
 * list and confirm screens: the stub is not focus-aware, so a keystroke would
 * reach both `TextInput`s at once. That leaves the editor — the entire reason
 * this panel is not read-only — asserted by nobody. This file mounts the real
 * component over a real hermes-ink input pipeline instead, so `focus`,
 * `useOverlayKeys` and both TextInputs behave as they do in the terminal, and
 * "you can create a room" is a fact rather than a claim.
 *
 * It also pins the IME/paste regression. hermes-ink coalesces bytes that arrive
 * together into ONE keypress event, so a commit immediately followed by Return
 * ("会議室\r") reaches `onSubmit` via `valueForReturnSubmit()` WITHOUT ever
 * passing through `onChange` — the contract `textInputSubmitClear.test.tsx`
 * pins on the TextInput side. A panel that read its React state in `onSubmit`
 * would drop that text; for a name typed entirely in one commit it would refuse
 * to save at all, complaining about a field the user can see is full.
 */

class FakeInput extends EventEmitter {
  chunks: string[] = []
  isRaw = false
  isTTY = true
  readableLength = 0

  read() {
    const next = this.chunks.shift() ?? null
    this.readableLength = this.chunks.length

    return next
  }

  ref = vi.fn()

  /** One `readable` per call: chunks passed together coalesce into one event. */
  send(...chunks: string[]) {
    this.chunks.push(...chunks)
    this.readableLength = this.chunks.length
    this.emit('readable')
  }

  setEncoding = vi.fn()

  setRawMode = vi.fn((enabled: boolean) => {
    this.isRaw = enabled
  })

  unref = vi.fn()
}

const settle = (ms = 25) => new Promise(resolve => setTimeout(resolve, ms))

interface StubCall {
  method: string
  params: Record<string, unknown>
}

function mount(rooms: unknown[]) {
  const stdin = new FakeInput()
  const stdout = new PassThrough()
  const stderr = new PassThrough()
  const calls: StubCall[] = []

  Object.assign(stdout, { columns: 100, isTTY: false, rows: 40 })
  Object.assign(stderr, { columns: 100, isTTY: false, rows: 40 })

  const gw = {
    request: (method: string, params: Record<string, unknown>) => {
      calls.push({ method, params })

      if (method === 'rooms.list') {
        return Promise.resolve({ rooms })
      }

      return Promise.resolve({ room: { id: 'room_new', memberIds: [], name: 'x' } })
    }
  } as unknown as GatewayClient

  const instance = renderSync(React.createElement(RoomsPanel, { gw, onClose: () => {}, t: DEFAULT_THEME }), {
    patchConsole: false,
    stderr: stderr as NodeJS.WriteStream,
    stdin: stdin as unknown as NodeJS.ReadStream,
    stdout: stdout as NodeJS.WriteStream
  })

  return {
    calls,
    cleanup: () => {
      instance.unmount()
      instance.cleanup()
    },
    stdin,
    /** The one write the panel made, or undefined if it made none. */
    write: () => calls.find(c => c.method !== 'rooms.list')
  }
}

const EXISTING = [{ id: 'room_1', memberIds: ['scout'], name: 'Launch Crew' }]

describe('RoomsPanel editor — the write path, over real stdin', () => {
  it('creates a room from a typed name and roster', async () => {
    const panel = mount([])

    await settle()
    panel.stdin.send('n')
    await settle()

    panel.stdin.send('Release Crew')
    await settle()
    panel.stdin.send('\r') // name submitted, focus moves to members
    await settle()

    panel.stdin.send('scout, smith')
    await settle()
    panel.stdin.send('\r') // members submitted, room saved
    await settle()

    expect(panel.write()).toEqual({
      method: 'rooms.create',
      params: { memberIds: ['scout', 'smith'], name: 'Release Crew' }
    })
    // ...and the list is re-read afterwards, so ordering comes from the store.
    expect(panel.calls.map(c => c.method)).toEqual(['rooms.list', 'rooms.create', 'rooms.list'])

    panel.cleanup()
  })

  it('keeps text that arrived in the same event as Return (IME/paste commit)', async () => {
    const panel = mount([])

    await settle()
    panel.stdin.send('n')
    await settle()

    // Both fields typed as a commit-plus-Return burst: `onChange` never fires
    // for this text, only `onSubmit` sees it.
    panel.stdin.send('会議室', '\r')
    await settle()
    panel.stdin.send('scout, smith', '\r')
    await settle()

    expect(panel.write()).toEqual({
      method: 'rooms.create',
      params: { memberIds: ['scout', 'smith'], name: '会議室' }
    })

    panel.cleanup()
  })

  it('edits the selected room in place, keeping its id', async () => {
    const panel = mount(EXISTING)

    await settle()
    panel.stdin.send('e')
    await settle()

    // The name field is prefilled; Enter accepts it unchanged.
    panel.stdin.send('\r')
    await settle()
    // The roster is prefilled too — append a second member to it.
    panel.stdin.send(', smith')
    await settle()
    panel.stdin.send('\r')
    await settle()

    expect(panel.write()).toEqual({
      method: 'rooms.update',
      params: { id: 'room_1', memberIds: ['scout', 'smith'], name: 'Launch Crew' }
    })

    panel.cleanup()
  })

  it('refuses to save a nameless room without asking the gateway', async () => {
    const panel = mount([])

    await settle()
    panel.stdin.send('n')
    await settle()
    panel.stdin.send('\r') // empty name → advance to members
    await settle()
    panel.stdin.send('scout')
    await settle()
    panel.stdin.send('\r') // save attempt
    await settle()

    expect(panel.write()).toBeUndefined()
    expect(panel.calls.map(c => c.method)).toEqual(['rooms.list'])

    panel.cleanup()
  })

  it('escapes out of the editor without writing anything', async () => {
    const panel = mount([])

    await settle()
    panel.stdin.send('n')
    await settle()
    panel.stdin.send('Abandoned')
    await settle()
    panel.stdin.send('\u001B') // Esc
    await settle()

    expect(panel.write()).toBeUndefined()

    panel.cleanup()
  })
})
