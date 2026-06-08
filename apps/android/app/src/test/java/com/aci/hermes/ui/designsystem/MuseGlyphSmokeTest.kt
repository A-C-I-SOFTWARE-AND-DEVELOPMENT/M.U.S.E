package com.aci.hermes.ui.designsystem

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.test.assertExists
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import com.aci.hermes.ui.theme.JarvisPrimeTheme
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/**
 * Compose smoke tests for the canvas-drawn marks ([MuseGlyph], [MuseStatusDot])
 * and the [DesignSystemGallery]. These components have no text, so the proof is
 * that they compose and lay out without throwing — the same compile-level +
 * render proof, asserted via a tagged wrapper. NATIVE graphics mode exercises
 * the real Compose draw pass under Robolectric (no emulator).
 */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [33])
class MuseGlyphSmokeTest {

    @get:Rule
    val composeRule = createComposeRule()

    @Test
    fun `glyph renders with and without bloom`() {
        composeRule.setContent {
            JarvisPrimeTheme {
                Box(modifier = Modifier.testTag("glyph-host")) {
                    Column {
                        MuseGlyph(showBloom = true)
                        MuseGlyph(showBloom = false)
                    }
                }
            }
        }

        composeRule.onNodeWithTag("glyph-host").assertExists()
    }

    @Test
    fun `every status dot state renders`() {
        composeRule.setContent {
            JarvisPrimeTheme {
                Box(modifier = Modifier.testTag("dot-host")) {
                    Column {
                        MuseStatusDot(status = MuseStatus.Off, animate = false)
                        MuseStatusDot(status = MuseStatus.Ok, animate = false)
                        MuseStatusDot(status = MuseStatus.Live, animate = false)
                        // Frozen pulse so the test is deterministic (no infinite anim).
                        MuseStatusDot(status = MuseStatus.Connecting, animate = false)
                    }
                }
            }
        }

        composeRule.onNodeWithTag("dot-host").assertExists()
    }

    @Test
    fun `gallery renders the full component catalog`() {
        composeRule.setContent {
            JarvisPrimeTheme {
                Box(modifier = Modifier.testTag("gallery-host")) {
                    DesignSystemGallery()
                }
            }
        }

        composeRule.onNodeWithTag("gallery-host").assertExists()
    }
}
