package com.aci.hermes.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.aci.hermes.R
import com.aci.hermes.ui.theme.JarvisCrimson
import com.aci.hermes.ui.theme.JarvisCyan
import com.aci.hermes.ui.theme.JarvisGold
import com.aci.hermes.ui.theme.JarvisInkRaised
import com.aci.hermes.ui.theme.JarvisJade
import com.aci.hermes.ui.theme.JarvisSignalDim
import com.aci.hermes.ui.theme.JarvisTokens
import com.aci.hermes.ui.theme.JarvisViolet

enum class GatewayStatus { ONLINE, LISTENING, WORKING, DISCONNECTED, MOCK, TERMUX }

private data class PillStyle(val dot: Color, val label: Color, val labelText: String)

@Composable
private fun styleFor(status: GatewayStatus): PillStyle = when (status) {
    GatewayStatus.ONLINE       -> PillStyle(JarvisJade,    JarvisJade,    stringResource(R.string.gateway_status_online))
    GatewayStatus.LISTENING    -> PillStyle(JarvisCyan,    JarvisCyan,    stringResource(R.string.gateway_status_listening))
    GatewayStatus.WORKING      -> PillStyle(JarvisGold,    JarvisGold,    stringResource(R.string.gateway_status_working))
    GatewayStatus.DISCONNECTED -> PillStyle(JarvisCrimson, JarvisCrimson, stringResource(R.string.gateway_status_disconnected))
    GatewayStatus.MOCK         -> PillStyle(JarvisViolet,  JarvisViolet,  stringResource(R.string.gateway_status_mock))
    GatewayStatus.TERMUX       -> PillStyle(JarvisCyan,    JarvisCyan,    stringResource(R.string.gateway_status_termux))
}

/**
 * Small status chip showing whether Jarvis can reach the local gateway.
 *
 * Colour-coded dot plus a one-word label. No animation by default; if a
 * caller wants the working/listening states to pulse, animate the
 * Surface's tint at the call site so reduced-motion users can opt out.
 */
@Composable
fun GatewayStatusPill(
    status: GatewayStatus,
    modifier: Modifier = Modifier,
) {
    val style = styleFor(status)
    Surface(
        shape = JarvisTokens.ShapePill,
        color = JarvisInkRaised,
        modifier = modifier
            .height(JarvisTokens.PillHeight)
            .border(
                width = JarvisTokens.BorderHairline,
                color = style.label.copy(alpha = 0.35f),
                shape = JarvisTokens.ShapePill
            )
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm),
            modifier = Modifier.padding(horizontal = JarvisTokens.SpaceMd)
        ) {
            Surface(
                shape = CircleShape,
                color = style.dot,
                modifier = Modifier.size(8.dp),
                content = {}
            )
            Text(
                text = stringResource(R.string.gateway_pill_label) + " · " + style.labelText,
                style = MaterialTheme.typography.labelMedium,
                color = JarvisSignalDim
            )
        }
    }
}
