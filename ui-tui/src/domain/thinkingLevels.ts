/** Reasoning / thinking effort levels supported by Hermes + Muse TUI. */

export type ThinkingEffort = 'none' | 'minimal' | 'low' | 'medium' | 'high' | 'xhigh'

export interface ThinkingLevelOption {
  /** Short status-bar label (empty = hide from chrome for default). */
  chrome: string
  hint: string
  id: ThinkingEffort
  label: string
}

export const THINKING_LEVELS: ThinkingLevelOption[] = [
  { chrome: 'none', hint: 'disable model thinking / CoT', id: 'none', label: 'None' },
  { chrome: 'min', hint: 'lightest reasoning budget', id: 'minimal', label: 'Minimal' },
  { chrome: 'low', hint: 'fast answers, light reasoning', id: 'low', label: 'Low' },
  { chrome: 'med', hint: 'balanced (default)', id: 'medium', label: 'Medium' },
  { chrome: 'high', hint: 'deeper reasoning, slower', id: 'high', label: 'High' },
  { chrome: 'xhigh', hint: 'maximum reasoning budget', id: 'xhigh', label: 'Extra high' }
]

export const THINKING_EFFORT_IDS = THINKING_LEVELS.map(l => l.id)

export const isThinkingEffort = (value: string): value is ThinkingEffort =>
  (THINKING_EFFORT_IDS as string[]).includes(value)

export const thinkingChromeLabel = (effort?: string) => {
  const value = String(effort ?? '')
    .trim()
    .toLowerCase()

  if (!value) {
    return ''
  }

  const hit = THINKING_LEVELS.find(l => l.id === value)

  return hit?.chrome ?? value
}

export const nextThinkingEffort = (current?: string): ThinkingEffort => {
  const value = String(current ?? 'medium')
    .trim()
    .toLowerCase()
  const idx = THINKING_EFFORT_IDS.indexOf(value as ThinkingEffort)

  if (idx < 0) {
    return 'medium'
  }

  return THINKING_EFFORT_IDS[(idx + 1) % THINKING_EFFORT_IDS.length]!
}
