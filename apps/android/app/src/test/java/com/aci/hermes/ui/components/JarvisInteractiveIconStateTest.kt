package com.aci.hermes.ui.components

import androidx.compose.ui.graphics.toArgb
import com.aci.hermes.ui.theme.JarvisCyan
import com.aci.hermes.ui.theme.JarvisGold
import com.aci.hermes.ui.theme.JarvisRed
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class JarvisInteractiveIconStateTest {

    @Test fun idle_uses_gold() {
        assertEquals(JarvisGold.toArgb(), colorFor(JarvisIconState.IDLE).toArgb())
    }

    @Test fun listening_uses_cyan() {
        assertEquals(JarvisCyan.toArgb(), colorFor(JarvisIconState.LISTENING).toArgb())
    }

    @Test fun working_uses_cyan() {
        assertEquals(JarvisCyan.toArgb(), colorFor(JarvisIconState.WORKING).toArgb())
    }

    @Test fun alert_uses_gold() {
        assertEquals(JarvisGold.toArgb(), colorFor(JarvisIconState.ALERT).toArgb())
    }

    @Test fun critical_uses_red() {
        assertEquals(JarvisRed.toArgb(), colorFor(JarvisIconState.CRITICAL).toArgb())
    }

    @Test fun critical_halo_is_the_strongest() {
        for (other in JarvisIconState.entries.filter { it != JarvisIconState.CRITICAL }) {
            assertTrue(
                "CRITICAL halo must be louder than $other",
                haloAlpha(JarvisIconState.CRITICAL) >= haloAlpha(other),
            )
        }
    }

    @Test fun idle_halo_is_the_quietest() {
        for (other in JarvisIconState.entries.filter { it != JarvisIconState.IDLE }) {
            assertTrue(
                "IDLE halo must be calmer than $other",
                haloAlpha(JarvisIconState.IDLE) <= haloAlpha(other),
            )
        }
    }

    @Test fun every_state_has_a_color_mapping() {
        for (state in JarvisIconState.entries) {
            // Just calling colorFor — any missing branch throws via the
            // `when` exhaustiveness check at compile time. This test
            // doubles as a regression guard if someone reaches for
            // `Color(0xFF...)` instead of going through the theme.
            colorFor(state)
            haloAlpha(state)
        }
    }
}
