package com.aci.hermes.ui.designsystem

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Bolt
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.aci.hermes.ui.components.EmptyState
import com.aci.hermes.ui.theme.JarvisInkAbyss
import com.aci.hermes.ui.theme.JarvisPrimeTheme
import com.aci.hermes.ui.theme.JarvisSignal
import com.aci.hermes.ui.theme.JarvisSignalMute
import com.aci.hermes.ui.theme.JarvisTokens

/**
 * A living gallery of the muse design system — every component rendered on the
 * void background, so a designer or reviewer can eyeball the whole language at
 * once (the "Read the rendered surface back and eyeball it" loop from the
 * brand doc). Also the canonical `@Preview` target.
 *
 * This composable is *not* a navigation screen; it has no ViewModel and no
 * side effects. It is a catalog.
 */
@Composable
fun DesignSystemGallery(modifier: Modifier = Modifier) {
    Column(
        modifier = modifier
            .fillMaxWidth()
            .background(JarvisInkAbyss)
            .verticalScroll(rememberScrollState())
            .padding(JarvisTokens.SpaceXxl),
        verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceXxl),
    ) {
        // --- The mark ---
        GallerySection("The mark") {
            Row(horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceXl)) {
                museGlyph(size = 88.dp)
                museGlyph(size = 48.dp)
                museGlyph(size = 24.dp, showBloom = false)
            }
        }

        // --- Buttons ---
        GallerySection("Buttons") {
            Column(verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm)) {
                Row(horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm)) {
                    museButton(onClick = {}, text = "Primary", variant = museButtonVariant.Primary)
                    museButton(onClick = {}, text = "Secondary", variant = museButtonVariant.Secondary)
                }
                Row(horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm)) {
                    museButton(onClick = {}, text = "Stop", variant = museButtonVariant.Danger)
                    museButton(
                        onClick = {},
                        text = "Approve",
                        variant = museButtonVariant.Approve,
                        leadingIcon = Icons.Filled.Bolt,
                    )
                    museButton(onClick = {}, text = "Disabled", enabled = false)
                }
            }
        }

        // --- Card ---
        GallerySection("Card") {
            museCard(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(JarvisTokens.SpaceLg)) {
                    museSectionHeader(
                        title = "Orchestrated job",
                        subtitle = "prompt-to-PR demo",
                        trailing = { museStatusPill(status = museStatus.Live, label = "Live") },
                    )
                    Text(
                        text = "A framed void-3 panel with an edge hairline.",
                        style = MaterialTheme.typography.bodyMedium,
                        color = JarvisSignalMute,
                        modifier = Modifier.padding(top = JarvisTokens.SpaceSm),
                    )
                }
            }
        }

        // --- Status dots & pills ---
        GallerySection("Status") {
            Column(verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm)) {
                Row(
                    horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceLg),
                ) {
                    museStatusDot(status = museStatus.Off)
                    museStatusDot(status = museStatus.Ok)
                    museStatusDot(status = museStatus.Live)
                    museStatusDot(status = museStatus.Connecting)
                }
                Row(horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm)) {
                    museStatusPill(status = museStatus.Off, label = "Offline")
                    museStatusPill(status = museStatus.Ok, label = "Paired")
                    museStatusPill(status = museStatus.Connecting, label = "Connecting")
                }
            }
        }

        // --- Chips ---
        GallerySection("Chips") {
            Row(horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm)) {
                museChip(label = "All")
                museChip(label = "Building", selected = true)
                museChip(label = "Merged", onClick = {})
            }
        }

        // --- Phase rail ---
        GallerySection("Phase rail") {
            musePhaseRail(
                phases = listOf(
                    musePhase("Plan", musePhaseState.Done),
                    musePhase("Build", musePhaseState.Current),
                    musePhase("Review", musePhaseState.Pending),
                    musePhase("Ship", musePhaseState.Pending),
                ),
            )
        }

        // --- Empty state ---
        GallerySection("Empty state") {
            museEmptyState(
                title = "No active jobs",
                body = "Start an orchestrated job and it will show up here with live phases.",
                actionLabel = "Start a job",
                onAction = {},
            )
        }

        // --- Motion + EmptyState (navigation motion spec + shared shell empty) ---
        GallerySection("Motion + EmptyState") {
            Column(verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceMd)) {
                museCard(modifier = Modifier.fillMaxWidth()) {
                    Column(modifier = Modifier.padding(JarvisTokens.SpaceLg)) {
                        museSectionHeader(
                            title = "Navigation motion",
                            subtitle = "museMotion tweens only — no springs",
                        )
                        Text(
                            text = "Tab swaps fade through: in " +
                                "${museMotion.DurationStandard}ms standard, out " +
                                "${museMotion.DurationFast}ms fast. Detail pushes arrive " +
                                "with intent: ${museMotion.DurationEmphasized}ms emphasized " +
                                "fade + an upward settle of 1/24 the height; the pop is " +
                                "the exact mirror. The core blazes, it does not wobble.",
                            style = MaterialTheme.typography.bodyMedium,
                            color = JarvisSignalMute,
                            modifier = Modifier.padding(top = JarvisTokens.SpaceSm),
                        )
                    }
                }
                // The cockpit-wide EmptyState: 48dp icon inside a 64dp matte
                // ring (1dp edge hairline — no glow, no shadow).
                EmptyState(
                    icon = Icons.Filled.Bolt,
                    title = "Nothing here yet",
                    body = "Absence reads as intentional: matte ring, value-only hierarchy.",
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        }
    }
}

@Composable
private fun GallerySection(title: String, content: @Composable () -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceMd)) {
        Text(
            text = title,
            style = MaterialTheme.typography.labelMedium,
            color = JarvisSignal,
        )
        content()
    }
}

@Preview(
    name = "muse design system",
    showBackground = true,
    backgroundColor = 0xFF050507,
    heightDp = 1400,
)
@Composable
private fun DesignSystemGalleryPreview() {
    JarvisPrimeTheme {
        DesignSystemGallery()
    }
}
