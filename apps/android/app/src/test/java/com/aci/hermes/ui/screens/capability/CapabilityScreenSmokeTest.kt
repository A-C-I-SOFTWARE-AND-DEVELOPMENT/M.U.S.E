package com.aci.hermes.ui.screens.capability

import android.app.Application
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.test.core.app.ApplicationProvider
import com.aci.hermes.data.capability.CapabilityRepository
import com.aci.hermes.ui.theme.HermesTheme
import com.aci.hermes.util.LogBuffer
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/**
 * Compose smoke test (Robolectric, no emulator) for [CapabilityScreen].
 *
 * Uses the 3-arg [CapabilityViewModel] (null cockpit client), so the live
 * "installed on gateway" section is a deterministic no-op that launches no
 * coroutines — the screen renders the curated catalog synchronously. Mirrors
 * PlaceholderScreenSmokeTest (no global Main-dispatcher override). The
 * installed-skills state branches are covered by [CapabilityViewModelTest].
 */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [33])
class CapabilityScreenSmokeTest {

    @get:Rule
    val composeRule = createComposeRule()

    @Test
    fun `renders the capabilities title`() {
        val app = ApplicationProvider.getApplicationContext<Application>()
        val viewModel = CapabilityViewModel(app, CapabilityRepository(), LogBuffer())
        composeRule.setContent {
            HermesTheme {
                CapabilityScreen(viewModel = viewModel, onBack = {})
            }
        }

        composeRule.onNodeWithText("Capabilities").assertIsDisplayed()
    }
}
