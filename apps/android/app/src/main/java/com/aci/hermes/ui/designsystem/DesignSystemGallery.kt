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
import com.aci.hermes.ui.theme.JarvisInkAbyss
import com.aci.hermes.ui.theme.JarvisPrimeTheme
import com.aci.hermes.ui.theme.JarvisSignal
import com.aci.hermes.ui.theme.JarvisSignalMute
import com.aci.hermes.ui.theme.JarvisTokens

/**
 * A living gallery of the MUSE design system — every component rendered on the
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
                MuseGlyph(size = 88.dp)
                MuseGlyph(size = 48.dp)
                MuseGlyph(size = 24.dp, showBloom = false)
            }
        }

        // --- Buttons ---
        GallerySection("Buttons") {
            Column(verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm)) {
                Row(horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm)) {
                    MuseButton(onClick = {}, text = "Primary", variant = MuseButtonVariant.Primary)
                    MuseButton(onClick = {}, text = "Secondary", variant = MuseButtonVariant.Secondary)
                }
                Row(horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm)) {
                    MuseButton(onClick = {}, text = "Stop", variant = MuseButtonVariant.Danger)
                    MuseButton(
                        onClick = {},
                        text = "Approve",
                        variant = MuseButtonVariant.Approve,
                        leadingIcon = Icons.Filled.Bolt,
                    )
                    MuseButton(onClick = {}, text = "Disabled", enabled = false)
                }
            }
        }

        // --- Card ---
        GallerySection("Card") {
            MuseCard(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(JarvisTokens.SpaceLg)) {
                    MuseSectionHeader(
                        title = "Orchestrated job",
                        subtitle = "prompt-to-PR demo",
                        trailing = { MuseStatusPill(status = MuseStatus.Live, label = "Live") },
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
                    MuseStatusDot(status = MuseStatus.Off)
                    MuseStatusDot(status = MuseStatus.Ok)
                    MuseStatusDot(status = MuseStatus.Live)
                    MuseStatusDot(status = MuseStatus.Connecting)
                }
                Row(horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm)) {
                    MuseStatusPill(status = MuseStatus.Off, label = "Offline")
                    MuseStatusPill(status = MuseStatus.Ok, label = "Paired")
                    MuseStatusPill(status = MuseStatus.Connecting, label = "Connecting")
                }
            }
        }

        // --- Chips ---
        GallerySection("Chips") {
            Row(horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm)) {
                MuseChip(label = "All")
                MuseChip(label = "Building", selected = true)
                MuseChip(label = "Merged", onClick = {})
            }
        }

        // --- Phase rail ---
        GallerySection("Phase rail") {
            MusePhaseRail(
                phases = listOf(
                    MusePhase("Plan", MusePhaseState.Done),
                    MusePhase("Build", MusePhaseState.Current),
                    MusePhase("Review", MusePhaseState.Pending),
                    MusePhase("Ship", MusePhaseState.Pending),
                ),
            )
        }

        // --- Empty state ---
        GallerySection("Empty state") {
            MuseEmptyState(
                title = "No active jobs",
                body = "Start an orchestrated job and it will show up here with live phases.",
                actionLabel = "Start a job",
                onAction = {},
            )
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
    name = "MUSE design system",
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
