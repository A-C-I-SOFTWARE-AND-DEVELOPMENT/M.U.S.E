package com.aci.hermes.ui.screens.live

import com.aci.hermes.ui.jarvis.JarvisPalette
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Test

/**
 * Guards that the Jarvis Live screen pulls its accent colors from the
 * canonical [JarvisPalette] rather than reintroducing a parallel
 * palette. If someone forks the colors here the icon and the screen
 * will drift visually; this test fails before that drift ships.
 */
class JarvisLivePaletteTest {

    @Test
    fun active_accent_matches_canonical_cyan() {
        assertEquals(JarvisPalette.Cyan, JarvisLiveColors.Active)
    }

    @Test
    fun approval_accent_matches_canonical_gold() {
        assertEquals(JarvisPalette.Gold, JarvisLiveColors.Approval)
    }

    @Test
    fun critical_accent_matches_canonical_red() {
        assertEquals(JarvisPalette.Red, JarvisLiveColors.Critical)
    }

    @Test
    fun background_is_dark_navy_not_pure_black() {
        // The directive is dark navy; pure black (#000000) would lose
        // the command-center contrast.
        val black = androidx.compose.ui.graphics.Color(0xFF000000)
        assertNotEquals(black, JarvisLiveColors.Background)
    }
}
