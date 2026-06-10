package com.aci.hermes.ui.screens.placeholder

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.aci.hermes.ui.designsystem.MuseCard
import com.aci.hermes.ui.designsystem.MuseGlyph
import com.aci.hermes.ui.theme.JarvisSignal
import com.aci.hermes.ui.theme.JarvisSignalDim
import com.aci.hermes.ui.theme.JarvisTokens

/**
 * Shell placeholder for MUSE sections whose full UI is still being
 * built (Chat, Approvals, Memory, Audit). The screen still lives in the
 * navigation graph so the bottom tab, deep links from Home, and back-stack
 * tests all work; it just shows a "Coming soon" panel.
 */
@Composable
fun PlaceholderScreen(
    paddingValues: PaddingValues,
    title: String,
    description: String,
    comingSoonNote: String,
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(paddingValues)
            .padding(JarvisTokens.SpaceXxl),
        verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceLg),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        MuseGlyph(size = 72.dp)
        Text(
            text = title,
            style = MaterialTheme.typography.headlineMedium,
            color = JarvisSignal,
        )
        Text(
            text = description,
            style = MaterialTheme.typography.bodyLarge,
            color = JarvisSignalDim,
            textAlign = TextAlign.Center,
        )
        MuseCard(
            modifier = Modifier.padding(top = JarvisTokens.SpaceLg),
        ) {
            Text(
                text = comingSoonNote,
                style = MaterialTheme.typography.bodyMedium,
                color = JarvisSignalDim,
                modifier = Modifier.padding(JarvisTokens.SpaceLg),
                textAlign = TextAlign.Center,
            )
        }
    }
}
