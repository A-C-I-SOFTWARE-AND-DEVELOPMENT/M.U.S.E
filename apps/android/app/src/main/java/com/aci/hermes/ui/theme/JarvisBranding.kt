package com.aci.hermes.ui.theme

/**
 * One place to pin Jarvis Prime cockpit copy so a future tagline tweak
 * doesn't fan out into every screen. The underlying app/package name
 * stays "Hermes Agent" — Jarvis Prime is the operator persona running
 * on top of the Hermes runtime, not a separate product, and the visible
 * launcher label is owned by [com.aci.hermes.R.string.app_name].
 */
object JarvisBranding {
    const val PRODUCT = "Hermes Agent"
    const val PERSONA = "Jarvis Prime"
    const val TAGLINE = "Your local AI operating partner"
    const val COCKPIT_LABEL = "Jarvis Prime Cockpit"
    const val HERO_GLYPH = "☤"
}
