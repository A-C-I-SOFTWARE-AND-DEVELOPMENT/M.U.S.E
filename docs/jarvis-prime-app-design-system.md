# MUSE — App Design System

This document is the canonical reference for the visual identity of the
Android app that ships under the user-facing name **MUSE**. The
Android package, application ID, and signing identity all remain
`com.aci.hermes` (and the foreground service is still backed by
`HermesService`) — but everything the user sees says MUSE.

Read this alongside:

- `docs/jarvis-prime-app-identity-migration.md` — compatibility / migration notes
- `docs/jarvis-prime-app-microcopy.md` — every user-facing string with rationale

---

## 1. Identity principles

MUSE is the **command center** for a personal AI agent. Three
principles drive every visual decision:

1. **Authority, not theatre.** The agent is competent. The UI should
   feel like a flight deck or trading terminal — calm, dense, decisive
   — not a toy.
2. **Permission is sacred.** Approvals, serious actions, and critical
   actions are visually distinct from everyday tasks. The user is
   never tricked into a state change.
3. **Show the work.** Status (online / listening / working) is always
   visible. The user never has to guess what the agent is doing.

---

## 2. Palette

The full token set lives in `apps/android/app/src/main/java/com/aci/hermes/ui/theme/Color.kt`.

### Foundation (dark-first)

| Token | Hex | Use |
|---|---|---|
| `JarvisInkAbyss` | `#05070D` | App background, scrim, splash |
| `JarvisInkNight` | `#0B1020` | Canvas under cards |
| `JarvisInkDeep` | `#101630` | Primary surface (cards) |
| `JarvisInkRaised` | `#161E3D` | Raised surface (chips, headers) |
| `JarvisInkEdge` | `#1F2A4C` | Borders, dividers |

### Foreground

| Token | Hex | Use |
|---|---|---|
| `JarvisSignal` | `#E7ECF7` | Primary text on dark |
| `JarvisSignalDim` | `#B7BFD4` | Secondary text |
| `JarvisSignalMute` | `#7C86A3` | Tertiary / metadata |
| `JarvisSignalGhost` | `#4A5374` | Disabled, placeholder |

### Accents — semantic, never decorative

| Token | Hex | Meaning |
|---|---|---|
| `JarvisGold` | `#E6B341` | Brand, approval, authority |
| `JarvisCyan` | `#38C6E0` | Listening, scanning, active |
| `JarvisCrimson` | `#E5484D` | Destructive, emergency stop |
| `JarvisJade` | `#3DD68C` | Task complete, healthy |
| `JarvisAmber` | `#F59E0B` | Warning, attention required |
| `JarvisViolet` | `#8A7CFF` | Memory, recall, history |

Each accent has `-Bright` (pressed/focused), `-Deep` (shadow/pressed-down),
and `-Glow` (20% alpha for halos) variants.

### Light surface fallback

MUSE is dark-first; the light scheme is a daylight courtesy.

| Token | Hex | Use |
|---|---|---|
| `JarvisPaper` | `#FAF9F6` | Light background |
| `JarvisPaperSoft` | `#F1EFE8` | Light surface |
| `JarvisInkOnPaper` | `#0E0E12` | Text on light |

---

## 3. Tier ladder

Every interactive surface maps to a **tier**. Tier drives colour,
border, and confirmation flow. Defined in `CommandCard.kt` as `CardTier`.

| Tier | Accent | When |
|---|---|---|
| `INFO` | none / edge | Calm informational card |
| `ACTIVE` | Gold | "MUSE is on this" |
| `LISTENING` | Cyan | Live capture / scanning |
| `APPROVAL` | Gold | User must approve before agent acts |
| `SERIOUS` | Amber | Meaningful but reversible change |
| `CRITICAL` | Crimson | Destructive / irreversible |
| `SUCCESS` | Jade | Task complete |
| `MEMORY` | Violet | Memory or audit-log surface |

**Rule:** never use an accent colour outside its tier. Gold cannot mean
"task complete." Crimson cannot mean "listening." If you are tempted to
mix, you almost certainly want a new tier.

---

## 4. Typography

Defined in `Type.kt`. Material 3 `Typography` populated with sans-serif
default (system font) at the following sizes:

| Slot | Size / weight | Use |
|---|---|---|
| `displayLarge` | 34sp SemiBold | Splash brand |
| `headlineMedium` | 22sp SemiBold | Screen titles |
| `titleLarge` | 18sp SemiBold | Header strap |
| `titleMedium` | 16sp Medium | Card titles |
| `titleSmall` | 14sp Medium | Section labels |
| `bodyLarge` / `bodyMedium` | 16/14sp Normal | Card body |
| `labelLarge` / `labelMedium` | 14/12sp Medium | Chips, pills, CTAs |
| `labelSmall` | 11sp **Mono** | Audit log, prompt preview, code-adjacent |

Monospace is reserved for code-adjacent surfaces only.

---

## 5. Shapes & spacing

Defined in `Tokens.kt` as `JarvisTokens`. 4dp baseline grid.

- **Spacing:** `SpaceXxs (2)`, `SpaceXs (4)`, `SpaceSm (8)`, `SpaceMd (12)`,
  `SpaceLg (16)`, `SpaceXl (20)`, `SpaceXxl (24)`, `SpaceXxxl (32)`.
- **Card radius:** `RadiusMd = 14dp` (default), `RadiusLg = 20dp` (headers),
  `RadiusXl = 28dp` (sheets).
- **Pills:** 26dp height, 14dp radius.
- **Borders:** hairline `1dp` for normal frame, `1.5dp` for focused.

---

## 6. Subtle glow

The "command-center" feel comes from a quiet, single-pass halo behind
brand elements — never an animated pulse. Default implementation:
`JarvisPrimeIcon` draws one `drawCircle` with `JarvisGoldGlow` (20% gold)
behind the rings.

**Reduced motion:** all glow is static. No card pulses, no shimmer, no
breathing animations by default. Where motion does ship (mic capture,
gateway working), wrap it behind a single `shouldReduceMotion()` check
and degrade to a static colour swap.

---

## 7. Components

All components live under
`apps/android/app/src/main/java/com/aci/hermes/ui/components/`.

| Component | Purpose |
|---|---|
| `JarvisPrimeIcon` | Brand glyph (two rings + prime dot) — splash, headers, empty states |
| `JarvisStatusHeader` | Top-of-screen identity strap with gateway status |
| `AskJarvisBar` | Single-line text input + mic + send |
| `GatewayStatusPill` | Tiny chip: Online / Listening / Working / Disconnected / Mock / Termux |
| `CommandCard` | Primitive — tier-coloured framed card |
| `TaskCard` | Generic task entry with status chip |
| `ApprovalCard` | Tier APPROVAL — gold |
| `SeriousActionCard` | Tier SERIOUS — amber |
| `CriticalActionCard` | Tier CRITICAL — crimson, deliberate confirm |
| `MemoryCard` | Tier MEMORY — violet, "remembered" / "corrected" |
| `AuditCard` | Tier MEMORY — entry to immutable action log |
| `EmergencyStopButton` | Full-width crimson; two-tap confirm |
| `PermissionEducationCard` | Explain a permission before the system prompt |

Every component is pure UI: caller owns state and callbacks.

---

## 8. Accessibility

- Minimum 4.5:1 contrast on body text; verified for Signal-on-InkDeep.
- Status meaning is always conveyed by **colour + label** (never colour
  alone) — see `GatewayStatusPill` (dot + "Online", "Disconnected", …).
- All icon-only buttons declare `contentDescription`.
- Touch targets ≥ 40dp.
- Reduced-motion default: no looping animations.

---

## 9. Iconography

Launcher: adaptive icon, two-layer.

- `ic_launcher_background.xml` — navy gradient + faint cross-hair grid.
- `ic_launcher_foreground.xml` — gold authority ring, cyan listening
  ring, **"J"** monogram, gold prime dot (the watchful eye).

In-app brand glyph: `JarvisPrimeIcon` (Compose `Canvas` render of the
same rings + dot). Scales to any density; no bitmaps.

Other in-app iconography uses Material Symbols (Compose `Icons.Filled.*`
and `Icons.AutoMirrored.Filled.*`).

---

## 10. What this design system intentionally rejects

- **Cartoon mascot.** No anthropomorphic robot. MUSE is an interface,
  not a character with a face.
- **Marketing gradients.** No purple-to-pink hero gradients. No glassy
  liquid backgrounds. The product is a tool, not a launch page.
- **Looping animation.** Reduced-motion users are first-class. Anything
  that moves earns its motion.
- **Decorative colour.** Every accent has a job. If a tone has no
  semantic meaning, it does not ship.
