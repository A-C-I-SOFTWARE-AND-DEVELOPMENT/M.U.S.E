package com.aci.hermes.ui.screens.placeholder

import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.unit.dp
import com.aci.hermes.ui.theme.HermesTheme
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/**
 * A JVM Compose smoke test (Robolectric, no emulator). It proves the
 * Compose-under-Robolectric harness renders a real navigation screen and that
 * its content is actually laid out and displayed — the feasibility proof the
 * verification matrix needs before deeper UI tests are layered on.
 */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [33])
class PlaceholderScreenSmokeTest {

    @get:Rule
    val composeRule = createComposeRule()

    @Test
    fun `placeholder screen renders its title and coming-soon note`() {
        composeRule.setContent {
            HermesTheme {
                PlaceholderScreen(
                    paddingValues = PaddingValues(0.dp),
                    title = "Chat",
                    description = "Talk to muse",
                    comingSoonNote = "Full chat is on the way.",
                )
            }
        }

        composeRule.onNodeWithText("Chat").assertIsDisplayed()
        composeRule.onNodeWithText("Full chat is on the way.").assertIsDisplayed()
    }

    @Test
    fun `placeholder screen shows the supplied description`() {
        composeRule.setContent {
            HermesTheme {
                PlaceholderScreen(
                    paddingValues = PaddingValues(0.dp),
                    title = "Approvals",
                    description = "Owner approval queue.",
                    comingSoonNote = "Approvals UI coming soon.",
                )
            }
        }

        composeRule.onNodeWithText("Owner approval queue.").assertIsDisplayed()
    }
}
