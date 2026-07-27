import { describe, expect, it } from 'vitest'

import { nextThinkingEffort, thinkingChromeLabel, THINKING_EFFORT_IDS } from './thinkingLevels.js'

describe('thinkingLevels', () => {
  it('cycles through every effort including none and xhigh', () => {
    let cur = 'none'

    for (let i = 0; i < THINKING_EFFORT_IDS.length; i++) {
      cur = nextThinkingEffort(cur)
    }

    expect(cur).toBe('none')
    expect(nextThinkingEffort('medium')).toBe('high')
    expect(nextThinkingEffort('xhigh')).toBe('none')
  })

  it('labels chrome for every level including medium', () => {
    expect(thinkingChromeLabel('medium')).toBe('med')
    expect(thinkingChromeLabel('minimal')).toBe('min')
    expect(thinkingChromeLabel('xhigh')).toBe('xhigh')
    expect(thinkingChromeLabel('')).toBe('')
  })
})
