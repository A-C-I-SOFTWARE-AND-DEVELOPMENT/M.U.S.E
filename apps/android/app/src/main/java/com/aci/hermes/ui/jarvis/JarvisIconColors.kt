package com.aci.hermes.ui.jarvis

import androidx.compose.ui.graphics.Color

/**
 * Canonical MUSE palette. Kept here (separate from
 * `ui/theme/Color.kt`) so the icon's visual contract is self-contained
 * and doesn't drift when the surrounding Material theme is retuned.
 *
 * Values carry the "Singularity" identity: one white core in the void
 * and a single thin spectral ring (cyan→violet). They mirror the
 * canonical tokens in `ui/theme/Color.kt` (and the cockpit's
 * `gateway/cockpit/static/tokens.css`) but are restated here on purpose
 * so retuning the Material theme can't silently drift the icon. No
 * gold-era literals remain — the icon never renders gold at rest.
 */
object JarvisPalette {
    val Cyan = Color(0xFF7AE0FF)       // --ring-1: listening glow (spectral ring, cyan end)
    val Gold = Color(0xFFFFFFFF)       // --core: white point of light (was the gold approval ring)
    val GoldDeep = Color(0xFF7AE0FF)   // --ring-1: idle spectral ring (was deep gold)
    val Red = Color(0xFFE5484D)        // serious / critical ring
    val Green = Color(0xFF34D399)      // completion flash
    val Violet = Color(0xFFB388FF)     // --ring-2: thinking (spectral ring, violet end)
    val Slate = Color(0xFF94A3B8)      // working
    val DimGray = Color(0xFF4B5563)    // offline
    val Amber = Color(0xFFF59E0B)      // warning
    val Charcoal = Color(0xFF1F2937)   // blocked
    val Core = Color(0xFFFFFFFF)       // --core: white default core fill
    val Void = Color(0xFF050507)       // --void: near-black command-center base
}

/**
 * Per-state visual recipe. The composable reads these values rather
 * than branching on [IconState] directly — keeps the renderer dumb and
 * the palette swappable.
 */
data class IconAppearance(
    val coreColor: Color,
    val ringColor: Color,
    val haloColor: Color,
    /** Multiplier on the base pulse amplitude. 0f disables the pulse. */
    val pulseAmplitude: Float,
    /** True when this state should be dimmed (alpha < 1f). */
    val dim: Boolean,
)

/**
 * Maps [IconState] → [IconAppearance]. The visual recipe is the
 * authoritative source for "what color is the gold ring vs. the
 * critical ring" — tests assert on this map, not on hex literals.
 */
object JarvisIconColors {

    fun appearanceFor(state: IconState): IconAppearance = when (state) {
        IconState.IDLE -> IconAppearance(
            coreColor = JarvisPalette.Core,
            ringColor = JarvisPalette.GoldDeep,
            haloColor = JarvisPalette.GoldDeep.copy(alpha = 0.15f),
            pulseAmplitude = 0.25f,
            dim = false,
        )
        IconState.LISTENING -> IconAppearance(
            coreColor = JarvisPalette.Cyan,
            ringColor = JarvisPalette.Cyan,
            haloColor = JarvisPalette.Cyan.copy(alpha = 0.35f),
            pulseAmplitude = 1.0f,
            dim = false,
        )
        IconState.THINKING -> IconAppearance(
            coreColor = JarvisPalette.Violet,
            ringColor = JarvisPalette.Violet,
            haloColor = JarvisPalette.Violet.copy(alpha = 0.25f),
            pulseAmplitude = 0.5f,
            dim = false,
        )
        IconState.SPEAKING -> IconAppearance(
            coreColor = JarvisPalette.Cyan,
            ringColor = JarvisPalette.Cyan,
            haloColor = JarvisPalette.Cyan.copy(alpha = 0.45f),
            pulseAmplitude = 0.8f,
            dim = false,
        )
        IconState.WORKING -> IconAppearance(
            coreColor = JarvisPalette.Slate,
            ringColor = JarvisPalette.Slate,
            haloColor = JarvisPalette.Slate.copy(alpha = 0.25f),
            pulseAmplitude = 0.4f,
            dim = false,
        )
        IconState.WAITING_FOR_APPROVAL -> IconAppearance(
            coreColor = JarvisPalette.Core,
            ringColor = JarvisPalette.Gold,
            haloColor = JarvisPalette.Gold.copy(alpha = 0.30f),
            pulseAmplitude = 0.55f,
            dim = false,
        )
        IconState.SERIOUS_ACTION_PENDING -> IconAppearance(
            coreColor = JarvisPalette.Gold,
            ringColor = JarvisPalette.Gold,
            haloColor = JarvisPalette.Gold.copy(alpha = 0.45f),
            pulseAmplitude = 0.9f,
            dim = false,
        )
        IconState.CRITICAL_ACTION_PENDING -> IconAppearance(
            coreColor = JarvisPalette.Red,
            ringColor = JarvisPalette.Red,
            haloColor = JarvisPalette.Red.copy(alpha = 0.50f),
            pulseAmplitude = 1.0f,
            dim = false,
        )
        IconState.BLOCKED -> IconAppearance(
            coreColor = JarvisPalette.Charcoal,
            ringColor = JarvisPalette.Red,
            haloColor = JarvisPalette.Red.copy(alpha = 0.20f),
            pulseAmplitude = 0f,
            dim = false,
        )
        IconState.WARNING -> IconAppearance(
            coreColor = JarvisPalette.Amber,
            ringColor = JarvisPalette.Amber,
            haloColor = JarvisPalette.Amber.copy(alpha = 0.30f),
            pulseAmplitude = 0.5f,
            dim = false,
        )
        IconState.COMPLETE -> IconAppearance(
            coreColor = JarvisPalette.Green,
            ringColor = JarvisPalette.Green,
            haloColor = JarvisPalette.Green.copy(alpha = 0.50f),
            pulseAmplitude = 0.8f,
            dim = false,
        )
        IconState.OFFLINE -> IconAppearance(
            coreColor = JarvisPalette.DimGray,
            ringColor = JarvisPalette.DimGray,
            haloColor = JarvisPalette.DimGray.copy(alpha = 0.10f),
            pulseAmplitude = 0f,
            dim = true,
        )
    }
}
