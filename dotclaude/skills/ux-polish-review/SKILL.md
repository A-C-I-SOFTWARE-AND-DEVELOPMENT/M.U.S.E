---
name: ux-polish-review
description: Polish-pass review for UI, mobile UX, onboarding clarity, accessibility, copy, demo flow, and professional feel. Use before any demo, store submission, or marketing push. Produces a prioritized punch list, not a redesign.
---

# UX Polish Review

## Use when

- A demo or investor call is imminent.
- A store submission or marketing push is imminent.
- A feature is functionally complete but never reviewed for feel.

## Surfaces

1. **First-run / onboarding** — time-to-value, required choices, skip
   path, empty states.
2. **Primary flow** — one-handed phone use, tap targets ≥ 44px,
   forgiving forms, single-step error recovery.
3. **Copy** — specific, human; no Lorem ipsum / TODOs / placeholders.
4. **Visual hierarchy** — one primary action per screen, consistent
   spacing, no orphaned UI.
5. **Loading / empty / error states** — present and recoverable on every
   async surface.
6. **Accessibility** — WCAG AA contrast, focus order, alt text, labeled
   inputs, keyboard nav, reduced-motion respected.
7. **Mobile specifics** — safe-area, keyboard avoidance, no hover-only
   affordances, gestures discoverable.
8. **Demo flow** — two-minute end-to-end without hacks.
9. **Marketing surfaces** — favicon, OG image, store icon, screenshots,
   app name consistent.
10. **Polish** — sub-300ms animations, no layout shift, no console errors
    on the happy path.

## Severity

- **BLOCKER** — would embarrass us in a demo.
- **HIGH** — visible quality gap, fix this sprint.
- **MEDIUM** — polish, fix before launch.
- **LOW** — nit.

## Output

```
## Surface reviewed
## Findings (severity, where, what, suggested fix)
## Demo readiness verdict: READY | NEEDS WORK | NOT DEMO-READY
## Single most impactful change
```

## Hard rules

- A finding without a route / component file / screenshot is not a finding.
- Accessibility BLOCKERS override visual polish.
- Polish, not redesign.
