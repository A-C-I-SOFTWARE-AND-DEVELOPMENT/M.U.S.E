package com.aci.hermes.ui.theme

import androidx.compose.ui.graphics.Color

// ---------------------------------------------------------------------------
// Jarvis Prime palette
//
// Visual identity for the app surface. The package and namespace stay
// com.aci.hermes for build / install compatibility, but the user-facing
// product is "Jarvis Prime" — a command-center for an agent that asks
// permission, confirms intent, and shows real work happening.
//
// Source of truth lives in docs/jarvis-prime-app-design-system.md.
// ---------------------------------------------------------------------------

// Foundation — deep navy / near-black command-center base
val JarvisInkAbyss   = Color(0xFF05070D) // app background, scrim
val JarvisInkNight   = Color(0xFF0B1020) // canvas under cards
val JarvisInkDeep    = Color(0xFF101630) // primary surface (cards)
val JarvisInkRaised  = Color(0xFF161E3D) // raised surface (chips, headers)
val JarvisInkEdge    = Color(0xFF1F2A4C) // borders, dividers, subtle frame
val JarvisInkGlass   = Color(0x141B2A57) // 8% glass overlay for hover/press

// Foreground — luminous off-white reading surface
val JarvisSignal     = Color(0xFFE7ECF7) // primary on-dark text
val JarvisSignalDim  = Color(0xFFB7BFD4) // secondary on-dark text
val JarvisSignalMute = Color(0xFF7C86A3) // tertiary / metadata
val JarvisSignalGhost = Color(0xFF4A5374) // disabled / placeholder

// Gold — approval, authority, identity accent
val JarvisGold        = Color(0xFFE6B341) // primary accent (CTAs, brand)
val JarvisGoldBright  = Color(0xFFF6CB5F) // pressed / focused
val JarvisGoldDeep    = Color(0xFFB2802A) // shadow / pressed-down
val JarvisGoldGlow    = Color(0x33E6B341) // 20% glow

// Cyan — listening, scanning, active agent activity
val JarvisCyan        = Color(0xFF38C6E0)
val JarvisCyanBright  = Color(0xFF6DDDF1)
val JarvisCyanDeep    = Color(0xFF1D8AA1)
val JarvisCyanGlow    = Color(0x3338C6E0)

// Red — destructive, emergency stop, critical action
val JarvisCrimson     = Color(0xFFE5484D)
val JarvisCrimsonBright = Color(0xFFFF6B70)
val JarvisCrimsonDeep   = Color(0xFFA31B20)
val JarvisCrimsonGlow   = Color(0x33E5484D)

// Green — task complete, healthy, all good
val JarvisJade        = Color(0xFF3DD68C)
val JarvisJadeBright  = Color(0xFF66E5A9)
val JarvisJadeDeep    = Color(0xFF1F7F50)
val JarvisJadeGlow    = Color(0x333DD68C)

// Amber — warning, attention required (lighter than gold so it doesn't clash)
val JarvisAmber       = Color(0xFFF59E0B)
val JarvisAmberGlow   = Color(0x33F59E0B)

// Violet — memory, recall, history (used in MemoryCard / AuditCard accents)
val JarvisViolet      = Color(0xFF8A7CFF)
val JarvisVioletGlow  = Color(0x338A7CFF)

// ---------------------------------------------------------------------------
// Light-surface fallbacks — kept restrained. Jarvis Prime is dark-first;
// light mode is a courtesy for daylight visibility.
// ---------------------------------------------------------------------------
val JarvisPaper       = Color(0xFFFAF9F6)
val JarvisPaperSoft   = Color(0xFFF1EFE8)
val JarvisInkOnPaper  = Color(0xFF0E0E12)

// ---------------------------------------------------------------------------
// Back-compat aliases.
//
// Existing screens reference HermesGold / HermesInk / HermesViolet / etc.
// We keep the names but re-point them at the Jarvis tokens so the visual
// shift is global without a sweeping rename. Anything new should reference
// the Jarvis* names directly.
// ---------------------------------------------------------------------------
val HermesGold         = JarvisGold
val HermesGoldDeep     = JarvisGoldDeep
val HermesInk          = JarvisInkAbyss
val HermesInkSoft      = JarvisInkDeep
val HermesPaper        = JarvisPaper
val HermesViolet       = JarvisViolet
val HermesError        = JarvisCrimson
val HermesSurfaceDim   = JarvisInkNight
val HermesSurfaceBright = JarvisPaperSoft
