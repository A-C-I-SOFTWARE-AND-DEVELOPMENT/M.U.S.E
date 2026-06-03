package com.aci.hermes.ui.components

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CloudOff
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import com.aci.hermes.R
import com.aci.hermes.data.cockpit.BackendStatus
import com.aci.hermes.ui.theme.JarvisTokens

/**
 * Small "Hermes backend" reachability pill. Deliberately labelled
 * distinctly from the local foreground-service row so the two states are
 * never confused — the local service can be running while the backend is
 * unreachable, and the user needs to see both honestly.
 */
@Composable
fun BackendStatusPill(
    status: BackendStatus,
    modifier: Modifier = Modifier,
) {
    GatewayStatusPill(
        status = status.toGatewayStatus(),
        modifier = modifier,
        label = stringResource(R.string.backend_pill_label),
    )
}

/**
 * Offline / error banner for the backend gateway. Shown only when the
 * backend is genuinely unreachable; reuses the existing
 * `gateway_disconnected_*` copy. Offers an explicit Retry and a jump to
 * Diagnostics rather than leaving the user guessing.
 */
@Composable
fun BackendOfflineBanner(
    status: BackendStatus,
    onRetry: () -> Unit,
    onOpenDiagnostics: () -> Unit,
    modifier: Modifier = Modifier,
) {
    if (!status.isOffline) return
    Card(
        modifier = modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.errorContainer,
        ),
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(JarvisTokens.SpaceLg),
            verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm),
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm),
            ) {
                Icon(
                    imageVector = Icons.Filled.CloudOff,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.error,
                )
                Text(
                    text = stringResource(R.string.gateway_disconnected_title),
                    style = MaterialTheme.typography.titleSmall,
                    color = MaterialTheme.colorScheme.onErrorContainer,
                )
            }
            Text(
                text = stringResource(R.string.gateway_disconnected_body),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onErrorContainer,
            )
            Row(horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm)) {
                OutlinedButton(onClick = onRetry) {
                    Text(stringResource(R.string.gateway_disconnected_retry))
                }
                TextButton(onClick = onOpenDiagnostics) {
                    Text(stringResource(R.string.gateway_disconnected_diagnose))
                }
            }
        }
    }
}
