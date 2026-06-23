package com.aci.hermes.ui.theme

import androidx.compose.ui.graphics.Color

// ---------------------------------------------------------------------------
// muse palette — the canonical "Singularity" look
//
// Visual identity for the app surface. The package and namespace stay
// com.aci.hermes for build / install compatibility, but the user-facing
// product is "muse" — a command-center for an agent that asks
// permission, confirms intent, and shows real work happening.
//
// Source of truth: gateway/cockpit/static/tokens.css (the browser cockpit's
// Singularity tokens). One white core in the void, a single thin spectral
// ring (cyan→violet). Token NAMES are kept so existing screens keep
// compiling; the VALUES now carry Singularity semantics — JarvisGold is the
// white --core (primary accent), JarvisCyan is the spectral --ring-1.
// ---------------------------------------------------------------------------

// Foundation — the void ladder (near-black command-center base)
val JarvisInkAbyss   = Color(0xFF050507) // --void: app background, scrim
val JarvisInkNight   = Color(0xFF0B0D12) // --void-2: canvas under cards
val JarvisInkDeep    = Color(0xFF12151D) // --void-3: primary surface (cards)
val JarvisInkRaised  = Color(0xFF161A24) // raised surface (chips, headers)
val JarvisInkEdge    = Color(0xFF1C2030) // --edge: borders, dividers, frame
val JarvisInkGlass   = Color(0x141C2030) // 8% glass overlay for hover/press

// Foreground — luminous off-white reading surface
val JarvisSignal     = Color(0xFFE8ECF4) // --signal: primary on-dark text
val JarvisSignalDim  = Color(0xFFAAB2C4) // --signal-dim: secondary on-dark
val JarvisSignalMute = Color(0xFF6B7388) // --signal-mute: tertiary / metadata
val JarvisSignalGhost = Color(0xFF454C60) // disabled / placeholder

// Core — the single point of light: primary accent / brand / identity
// (name kept as "Gold" for back-compat; value is the white --core)
val JarvisGold        = Color(0xFFFFFFFF) // --core: primary accent (CTAs, brand)
val JarvisGoldBright  = Color(0xFFFFFFFF) // pressed / focused
val JarvisGoldDeep    = Color(0xFFC9CEDA) // shadow / pressed-down (dimmed core)
val JarvisGoldGlow    = Color(0x33FFFFFF) // 20% glow

// Spectral ring (cyan end) — listening, scanning, active agent activity
// (name kept as "Cyan" for back-compat; value is --ring-1)
val JarvisCyan        = Color(0xFF7AE0FF) // --ring-1
val JarvisCyanBright  = Color(0xFFA6ECFF)
val JarvisCyanDeep    = Color(0xFF3F9FC4)
val JarvisCyanGlow    = Color(0x337AE0FF)

// Danger — destructive, emergency stop, critical action
val JarvisCrimson     = Color(0xFFFF5C63) // --danger
val JarvisCrimsonBright = Color(0xFFFF888D)
val JarvisCrimsonDeep   = Color(0xFFB23036)
val JarvisCrimsonGlow   = Color(0x33FF5C63)

// Ok — task complete, healthy, all good
val JarvisJade        = Color(0xFF5BE3A0) // --ok
val JarvisJadeBright  = Color(0xFF85ECBA)
val JarvisJadeDeep    = Color(0xFF2F9A6A)
val JarvisJadeGlow    = Color(0x335BE3A0)

// Warn — warning, attention required
val JarvisAmber       = Color(0xFFF5C451) // --warn
val JarvisAmberGlow   = Color(0x33F5C451)

// Spectral ring (violet end) — memory, recall, history (MemoryCard / AuditCard)
// (name kept as "Violet"; value is --ring-2)
val JarvisViolet      = Color(0xFFB388FF) // --ring-2
val JarvisVioletGlow  = Color(0x33B388FF)

// ---------------------------------------------------------------------------
// Light-surface fallbacks — kept restrained. muse is dark-first;
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
val HermesCyan         = JarvisCyan
val HermesCrimson      = JarvisCrimson
val HermesError        = JarvisCrimson
val HermesSurfaceDim   = JarvisInkNight
val HermesSurfaceBright = JarvisPaperSoft
