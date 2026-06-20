package com.aci.hermes.ui.designsystem

import androidx.compose.foundation.layout.Column
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import com.aci.hermes.ui.theme.JarvisPrimeTheme
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/**
 * Compose smoke tests (Robolectric, no emulator) for the MUSE design-system
 * components. Each composes a component under [JarvisPrimeTheme] and proves it
 * builds and renders without crashing — the compile-level + basic-semantics
 * proof the verification matrix needs. Mirrors the existing
 * DiagnosticsScreenSmokeTest harness exactly
 * (RobolectricTestRunner, NATIVE graphics, SDK 33, no Main-dispatcher override).
 */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [33])
class MuseComponentsSmokeTest {

    @get:Rule
    val composeRule = createComposeRule()

    @Test
    fun `every button variant renders its label`() {
        composeRule.setContent {
            JarvisPrimeTheme {
                Column {
                    MuseButton(onClick = {}, text = "Primary", variant = MuseButtonVariant.Primary)
                    MuseButton(onClick = {}, text = "Secondary", variant = MuseButtonVariant.Secondary)
                    MuseButton(onClick = {}, text = "Stop", variant = MuseButtonVariant.Danger)
                    MuseButton(onClick = {}, text = "Approve", variant = MuseButtonVariant.Approve)
                    MuseButton(onClick = {}, text = "Off", enabled = false)
                }
            }
        }

        composeRule.onNodeWithText("Primary").assertIsDisplayed()
        composeRule.onNodeWithText("Secondary").assertIsDisplayed()
        composeRule.onNodeWithText("Stop").assertIsDisplayed()
        composeRule.onNodeWithText("Approve").assertIsDisplayed()
        composeRule.onNodeWithText("Off").assertIsDisplayed()
    }

    @Test
    fun `card renders its content`() {
        composeRule.setContent {
            JarvisPrimeTheme {
                MuseCard {
                    com.aci.hermes.ui.designsystem.MuseSectionHeader(title = "Job")
                }
            }
        }

        composeRule.onNodeWithText("Job").assertIsDisplayed()
    }

    @Test
    fun `status pill renders its label`() {
        composeRule.setContent {
            JarvisPrimeTheme {
                Column {
                    MuseStatusPill(status = MuseStatus.Off, label = "Offline", animate = false)
                    MuseStatusPill(status = MuseStatus.Ok, label = "Paired", animate = false)
                    MuseStatusPill(status = MuseStatus.Connecting, label = "Connecting", animate = false)
                }
            }
        }

        composeRule.onNodeWithText("Offline").assertIsDisplayed()
        composeRule.onNodeWithText("Paired").assertIsDisplayed()
        composeRule.onNodeWithText("Connecting").assertIsDisplayed()
    }

    @Test
    fun `chip renders selected and clickable variants`() {
        composeRule.setContent {
            JarvisPrimeTheme {
                Column {
                    MuseChip(label = "All")
                    MuseChip(label = "Building", selected = true)
                    MuseChip(label = "Merged", onClick = {})
                }
            }
        }

        composeRule.onNodeWithText("All").assertIsDisplayed()
        composeRule.onNodeWithText("Building").assertIsDisplayed()
        composeRule.onNodeWithText("Merged").assertIsDisplayed()
    }

    @Test
    fun `section header renders title, subtitle and trailing slot`() {
        composeRule.setContent {
            JarvisPrimeTheme {
                MuseSectionHeader(
                    title = "Recent jobs",
                    subtitle = "last 7 days",
                    trailing = { MuseStatusPill(status = MuseStatus.Ok, label = "Synced", animate = false) },
                )
            }
        }

        composeRule.onNodeWithText("Recent jobs").assertIsDisplayed()
        composeRule.onNodeWithText("last 7 days").assertIsDisplayed()
        composeRule.onNodeWithText("Synced").assertIsDisplayed()
    }

    @Test
    fun `empty state renders glyph, copy and action`() {
        composeRule.setContent {
            JarvisPrimeTheme {
                MuseEmptyState(
                    title = "No active jobs",
                    body = "Start a job to see live phases.",
                    actionLabel = "Start a job",
                    onAction = {},
                )
            }
        }

        composeRule.onNodeWithText("No active jobs").assertIsDisplayed()
        composeRule.onNodeWithText("Start a job to see live phases.").assertIsDisplayed()
        composeRule.onNodeWithText("Start a job").assertIsDisplayed()
    }

    @Test
    fun `phase rail renders every phase label`() {
        composeRule.setContent {
            JarvisPrimeTheme {
                MusePhaseRail(
                    phases = listOf(
                        MusePhase("Plan", MusePhaseState.Done),
                        MusePhase("Build", MusePhaseState.Current),
                        MusePhase("Review", MusePhaseState.Failed),
                        MusePhase("Ship", MusePhaseState.Pending),
                    ),
                )
            }
        }

        composeRule.onNodeWithText("Plan").assertIsDisplayed()
        composeRule.onNodeWithText("Build").assertIsDisplayed()
        composeRule.onNodeWithText("Review").assertIsDisplayed()
        composeRule.onNodeWithText("Ship").assertIsDisplayed()
    }
}
