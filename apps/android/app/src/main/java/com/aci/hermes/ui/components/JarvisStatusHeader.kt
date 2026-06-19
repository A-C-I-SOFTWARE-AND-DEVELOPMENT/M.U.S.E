package com.aci.hermes.ui.components

import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.aci.hermes.R
import com.aci.hermes.ui.theme.JarvisInkDeep
import com.aci.hermes.ui.theme.JarvisInkEdge
import com.aci.hermes.ui.theme.JarvisSignal
import com.aci.hermes.ui.theme.JarvisSignalDim
import com.aci.hermes.ui.theme.JarvisTokens

/**
 * Top-of-screen identity bar for the command center.
 *
 * Left: brand glyph + "muse" + subtitle.
 * Right: gateway status pill.
 *
 * Designed to sit in a Scaffold's content slot rather than the topBar
 * slot, because we want the framed-card aesthetic of the rest of the
 * surface (hairline gold edge, raised navy fill).
 */
@Composable
fun JarvisStatusHeader(
    gatewayStatus: GatewayStatus,
    modifier: Modifier = Modifier,
    title: String = stringResource(R.string.orchestrator_title),
    subtitle: String = stringResource(R.string.orchestrator_subtitle),
) {
    Surface(
        shape = JarvisTokens.ShapeCardLarge,
        color = JarvisInkDeep,
        modifier = modifier
            .fillMaxWidth()
            .border(
                width = JarvisTokens.BorderHairline,
                color = JarvisInkEdge,
                shape = JarvisTokens.ShapeCardLarge
            )
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceLg),
            modifier = Modifier.padding(
                horizontal = JarvisTokens.SpaceLg,
                vertical = JarvisTokens.SpaceMd
            )
        ) {
            JarvisPrimeIcon(size = 40.dp, showGlow = true)
            Column(
                modifier = Modifier
                    .weight(1f, fill = true),
                verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceXxs)
            ) {
                Text(
                    text = title,
                    style = MaterialTheme.typography.titleLarge,
                    color = JarvisSignal
                )
                Text(
                    text = subtitle,
                    style = MaterialTheme.typography.labelMedium,
                    color = JarvisSignalDim
                )
            }
            GatewayStatusPill(status = gatewayStatus)
        }
    }
}
