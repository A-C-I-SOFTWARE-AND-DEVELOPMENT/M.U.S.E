import { describe, expect, it } from 'vitest'

import { sidebarColumns, SIDEBAR_WIDTH, usableColumns } from '../components/cockpitSidebar.js'

/**
 * The sidebar is a RESERVED column: whatever it takes, the rest of the shell
 * must not also try to use. Every surface derives its width from
 * `usableColumns`, so these two functions have to stay exactly complementary —
 * if they ever drift, the transcript renders into space the sidebar owns and
 * spills off the right edge, which is not something a type checker can catch.
 */
describe('cockpit sidebar layout', () => {
  it('never overlaps the pane: sidebar + usable === total', () => {
    for (const total of [20, 40, 80, 85, 86, 100, 120, 200, 400]) {
      expect(sidebarColumns(total) + usableColumns(total)).toBe(total)
    }
  })

  it('hides itself rather than squeezing a narrow terminal', () => {
    // Below the threshold the sidebar takes nothing and the pane keeps the
    // full width — a chat pane under ~60 columns is worse than no sidebar.
    expect(sidebarColumns(80)).toBe(0)
    expect(usableColumns(80)).toBe(80)
  })

  it('reserves its full width once the terminal can afford it', () => {
    expect(sidebarColumns(200)).toBe(SIDEBAR_WIDTH)
    expect(usableColumns(200)).toBe(200 - SIDEBAR_WIDTH)
  })

  it('leaves the pane at least 60 columns whenever it is shown', () => {
    // The threshold exists to guarantee this; assert the guarantee, not the
    // constant, so tuning SIDEBAR_WIDTH cannot silently break it.
    for (let total = 1; total <= 400; total += 1) {
      if (sidebarColumns(total) > 0) {
        expect(usableColumns(total)).toBeGreaterThanOrEqual(60)
      }
    }
  })

  it('never returns a non-positive width', () => {
    for (const total of [0, 1, 2, 10]) {
      expect(usableColumns(total)).toBeGreaterThan(0)
    }
  })
})
