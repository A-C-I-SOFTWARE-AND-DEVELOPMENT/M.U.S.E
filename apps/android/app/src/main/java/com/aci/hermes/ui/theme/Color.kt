package com.aci.hermes.ui.theme

import androidx.compose.ui.graphics.Color

/**
 * Jarvis Prime palette.
 *
 * Dark navy / black is the foundation. Gold marks owner authority and
 * approval surfaces. Cyan marks listening / activity. Red marks
 * serious / critical danger. Green marks completion. Every accent is
 * pulled from this file — no Compose call sites should hand-roll a
 * Color literal.
 */

// ── Foundation ─────────────────────────────────────────────────────────
val JarvisInk = Color(0xFF06070C)            // near-black, app background
val JarvisNavy = Color(0xFF0B1220)           // dark navy, primary surface
val JarvisNavyElevated = Color(0xFF131C2E)   // raised cards, sheets
val JarvisNavyMuted = Color(0xFF1B2540)      // dividers, chip backgrounds
val JarvisFog = Color(0xFFE6E9F2)            // primary on-dark text
val JarvisFogDim = Color(0xFFA9B0C0)         // secondary on-dark text

// ── Authority (Owner / Approvals) ──────────────────────────────────────
val JarvisGold = Color(0xFFFFD24A)           // primary gold for authority
val JarvisGoldDeep = Color(0xFFC9961F)       // pressed / outline state

// ── Activity (Listening / Streaming) ───────────────────────────────────
val JarvisCyan = Color(0xFF4DD0E1)           // listening, voice, streaming
val JarvisCyanDeep = Color(0xFF1D8DA0)

// ── Danger (Serious / Critical) ────────────────────────────────────────
val JarvisRed = Color(0xFFEF4A4A)            // critical, emergency stop
val JarvisRedDeep = Color(0xFFB12525)

// ── Completion ─────────────────────────────────────────────────────────
val JarvisGreen = Color(0xFF4ADE80)          // completed, healthy
val JarvisGreenDeep = Color(0xFF1F8A3D)

// ── Legacy aliases (kept so older call sites compile during transform) ─
val HermesGold = JarvisGold
val HermesGoldDeep = JarvisGoldDeep
val HermesInk = JarvisInk
val HermesInkSoft = JarvisNavy
val HermesPaper = JarvisFog
val HermesViolet = JarvisCyan
val HermesError = JarvisRed
val HermesSurfaceDim = JarvisNavyElevated
val HermesSurfaceBright = JarvisFog
