package com.aci.hermes.ui.screens.live

import androidx.compose.ui.graphics.Color
import com.aci.hermes.ui.jarvis.JarvisPalette

/**
 * Color tokens for the full-screen Jarvis Live command screen.
 *
 * The screen is **dark-navy / gold / cyan** by directive — a
 * command-center aesthetic. Every value here is derived from the
 * canonical `JarvisPalette` (in `ui/jarvis/JarvisIconColors`) plus
 * one navy background — we do **not** introduce a parallel palette,
 * so the live screen tracks the icon's color contract automatically.
 */
object JarvisLiveColors {
    /** Deep navy background — command center cockpit. */
    val Background: Color = Color(0xFF0A0F1F)

    /** Slightly elevated surface (cards, status pill). */
    val Surface: Color = Color(0xFF111933)

    /** Primary "active" accent — borrows the listening glow. */
    val Active: Color = JarvisPalette.Cyan

    /** Approval / serious-action accent — gold ring. */
    val Approval: Color = JarvisPalette.Gold

    /** Critical / blocked accent — red. */
    val Critical: Color = JarvisPalette.Red

    /** Idle status text color. */
    val OnBackgroundMuted: Color = Color(0xFFB6C0E0)

    /** Primary status text color. */
    val OnBackground: Color = Color(0xFFEDF1FA)
}
