package com.aci.hermes.ui.theme

import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class JarvisPaletteTest {

    @Test fun foundation_is_dark() {
        assertTrue("Ink must be near-black", JarvisInk.relativeLuminance() < 0.02f)
        assertTrue("Navy must be dark", JarvisNavy.relativeLuminance() < 0.05f)
    }

    @Test fun gold_is_authority_color_and_distinct_from_cyan() {
        assertNotEquals(JarvisGold.toArgb(), JarvisCyan.toArgb())
        assertNotEquals(JarvisGold.toArgb(), JarvisRed.toArgb())
        assertNotEquals(JarvisGold.toArgb(), JarvisGreen.toArgb())
    }

    @Test fun completion_is_distinct_from_danger() {
        assertNotEquals(JarvisGreen.toArgb(), JarvisRed.toArgb())
    }

    @Test fun legacy_aliases_resolve_to_jarvis_tokens() {
        assertEquals(JarvisGold.toArgb(), HermesGold.toArgb())
        assertEquals(JarvisInk.toArgb(), HermesInk.toArgb())
        assertEquals(JarvisRed.toArgb(), HermesError.toArgb())
        // The "violet" alias is repurposed as cyan now — the rename is
        // intentional because the legacy color was never on-brand.
        assertEquals(JarvisCyan.toArgb(), HermesViolet.toArgb())
    }

    /** Simple sRGB relative luminance (WCAG 2.x), tests only. */
    private fun Color.relativeLuminance(): Float {
        fun chan(c: Float): Float = if (c <= 0.03928f) c / 12.92f
            else Math.pow(((c + 0.055f) / 1.055f).toDouble(), 2.4).toFloat()
        return 0.2126f * chan(red) + 0.7152f * chan(green) + 0.0722f * chan(blue)
    }
}
