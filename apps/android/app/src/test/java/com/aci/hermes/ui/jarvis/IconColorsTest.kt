package com.aci.hermes.ui.jarvis

import androidx.compose.ui.graphics.Color
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Pins the avatar icon's "Singularity" identity: a white core in the
 * void with a single spectral ring (cyan→violet). Guards against the
 * gold-era palette creeping back into any at-rest state — the icon must
 * never render gold while the assistant is simply idle, waiting, or
 * flagging a serious action.
 */
class IconColorsTest {

    /** Gold-era literals that must not appear as an at-rest ring color. */
    private val goldEra = setOf(Color(0xFFFFD700), Color(0xFFB8860B))

    /** Singularity tokens, restated from `ui/theme/Color.kt`. */
    private val core = Color(0xFFFFFFFF) // --core
    private val ring1 = Color(0xFF7AE0FF) // --ring-1 (cyan end)
    private val ring2 = Color(0xFFB388FF) // --ring-2 (violet end)

    /**
     * States the user sees with no active work in flight. These are the
     * ones that historically leaked gold; none of them may now.
     */
    private val atRestStates = listOf(
        IconState.IDLE,
        IconState.WAITING_FOR_APPROVAL,
        IconState.SERIOUS_ACTION_PENDING,
    )

    @Test
    fun `no at-rest state renders a gold-era ring`() {
        atRestStates.forEach { state ->
            val ring = JarvisIconColors.appearanceFor(state).ringColor
            assertTrue(
                "$state still uses a gold-era ring color: $ring",
                ring !in goldEra,
            )
        }
    }

    @Test
    fun `no at-rest state renders a gold-era core`() {
        atRestStates.forEach { state ->
            val coreColor = JarvisIconColors.appearanceFor(state).coreColor
            assertTrue(
                "$state still uses a gold-era core color: $coreColor",
                coreColor !in goldEra,
            )
        }
    }

    @Test
    fun `palette retires the gold-era literals entirely`() {
        // The two literals the old gold identity hung on.
        assertNotEquals(Color(0xFFFFD700), JarvisPalette.Gold)
        assertNotEquals(Color(0xFFB8860B), JarvisPalette.GoldDeep)
    }

    @Test
    fun `idle renders the singularity core and spectral ring`() {
        val idle = JarvisIconColors.appearanceFor(IconState.IDLE)
        assertEquals("idle core must be the white --core", core, idle.coreColor)
        assertEquals("idle ring must be the spectral --ring-1", ring1, idle.ringColor)
    }

    @Test
    fun `palette tokens match the canonical singularity values`() {
        assertEquals(core, JarvisPalette.Core)
        assertEquals(core, JarvisPalette.Gold)
        assertEquals(ring1, JarvisPalette.Cyan)
        assertEquals(ring1, JarvisPalette.GoldDeep)
        assertEquals(ring2, JarvisPalette.Violet)
        assertEquals(Color(0xFF050507), JarvisPalette.Void)
    }
}
