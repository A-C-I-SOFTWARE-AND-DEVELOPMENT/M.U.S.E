package com.aci.hermes.ui.screens.diagnostics

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import com.aci.hermes.ui.theme.HermesTheme
import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/**
 * Compose smoke test (Robolectric, no emulator) for [DiagnosticsScreen].
 *
 * Uses a null cockpit client so the backend probe short-circuits — the screen
 * renders fully synchronously with no network — and asserts the static chrome
 * is laid out. Proves the screen composes under the harness; the backend-state
 * branches are covered by [DiagnosticsViewModelTest].
 */
@OptIn(ExperimentalCoroutinesApi::class)
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [33])
class DiagnosticsScreenSmokeTest {

    @get:Rule
    val composeRule = createComposeRule()

    private val dispatcher = UnconfinedTestDispatcher()

    @Before fun setUp() { Dispatchers.setMain(dispatcher) }
    @After fun tearDown() { Dispatchers.resetMain() }

    @Test
    fun `renders the title and app-version row`() {
        val viewModel = DiagnosticsViewModel(LogBuffer(), cockpitClient = null)
        composeRule.setContent {
            HermesTheme {
                DiagnosticsScreen(viewModel = viewModel, onBack = {})
            }
        }

        composeRule.onNodeWithText("Diagnostics").assertIsDisplayed()
        composeRule.onNodeWithText("App version").assertIsDisplayed()
    }
}
