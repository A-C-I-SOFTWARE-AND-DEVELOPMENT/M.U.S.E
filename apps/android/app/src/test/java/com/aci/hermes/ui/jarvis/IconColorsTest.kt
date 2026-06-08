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
 *
 * Also pins the attention-escalation ramp introduced in FU-17b so the
 * three at-rest/attention states stay visually distinct from one
 * another. FU-17 mapped the old gold to white, which collapsed WAITING
 * and SERIOUS to an identical white core + white ring (and made both
 * nearly indistinguishable from IDLE). The ramp restores distinctness:
 *   IDLE     = white core + cyan (--ring-1) ring
 *   WAITING  = white core + violet (--ring-2) ring
 *   SERIOUS  = violet core + violet (--ring-2) ring
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
    fun `waiting for approval renders white core and violet ring`() {
        val waiting = JarvisIconColors.appearanceFor(IconState.WAITING_FOR_APPROVAL)
        assertEquals("waiting core must be the white --core", core, waiting.coreColor)
        assertEquals("waiting ring must be the spectral --ring-2 (violet)", ring2, waiting.ringColor)
    }

    @Test
    fun `serious action pending renders violet core and violet ring`() {
        val serious = JarvisIconColors.appearanceFor(IconState.SERIOUS_ACTION_PENDING)
        assertEquals("serious core must be the spectral --ring-2 (violet)", ring2, serious.coreColor)
        assertEquals("serious ring must be the spectral --ring-2 (violet)", ring2, serious.ringColor)
    }

    @Test
    fun `idle, waiting and serious are mutually distinct`() {
        val idle = JarvisIconColors.appearanceFor(IconState.IDLE)
        val waiting = JarvisIconColors.appearanceFor(IconState.WAITING_FOR_APPROVAL)
        val serious = JarvisIconColors.appearanceFor(IconState.SERIOUS_ACTION_PENDING)

        // Each pair must differ in at least one of {core, ring}. A state is a
        // (core, ring) pair; identical pairs render identically.
        assertNotEquals(
            "idle and waiting must be visually distinct",
            idle.coreColor to idle.ringColor,
            waiting.coreColor to waiting.ringColor,
        )
        assertNotEquals(
            "waiting and serious must be visually distinct",
            waiting.coreColor to waiting.ringColor,
            serious.coreColor to serious.ringColor,
        )
        assertNotEquals(
            "idle and serious must be visually distinct",
            idle.coreColor to idle.ringColor,
            serious.coreColor to serious.ringColor,
        )
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
