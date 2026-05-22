package com.aci.hermes.ui.screens.setup

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.aci.hermes.R
import com.aci.hermes.ui.theme.HermesGold

/**
 * First-run setup. Replaces the old "Get started / Skip" pair with three
 * named paths so the recommended phone-only flow (Direct API) is obvious.
 *
 * The three callbacks let the nav graph decide which destination each
 * card opens — the screen itself doesn't know whether a path needs the
 * Provider editor, a quick mode-flip into Mock, or something else.
 */
@Composable
fun SetupScreen(
    onUseDirectApi: () -> Unit,
    onUseDemoMode: () -> Unit,
    onConnectHermesGateway: () -> Unit
) {
    Scaffold { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 20.dp, vertical = 24.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Text(
                text = "☤",
                color = HermesGold,
                style = MaterialTheme.typography.displayLarge
            )
            Text(
                text = stringResource(R.string.setup_welcome_title),
                style = MaterialTheme.typography.headlineMedium,
                color = MaterialTheme.colorScheme.onBackground
            )
            Text(
                text = stringResource(R.string.setup_welcome_subtitle),
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onBackground
            )
            Spacer(modifier = Modifier.height(8.dp))

            SetupOptionCard(
                title = stringResource(R.string.setup_card_direct_title),
                description = stringResource(R.string.setup_card_direct_description),
                cta = stringResource(R.string.setup_card_direct_cta),
                tag = stringResource(R.string.setup_tag_recommended),
                primary = true,
                onClick = onUseDirectApi
            )
            SetupOptionCard(
                title = stringResource(R.string.setup_card_demo_title),
                description = stringResource(R.string.setup_card_demo_description),
                cta = stringResource(R.string.setup_card_demo_cta),
                tag = null,
                primary = false,
                onClick = onUseDemoMode
            )
            SetupOptionCard(
                title = stringResource(R.string.setup_card_hermes_title),
                description = stringResource(R.string.setup_card_hermes_description),
                cta = stringResource(R.string.setup_card_hermes_cta),
                tag = stringResource(R.string.setup_tag_advanced),
                primary = false,
                onClick = onConnectHermesGateway
            )

            Spacer(modifier = Modifier.height(16.dp))
            Text(
                text = stringResource(R.string.setup_companion_note),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurface
            )
        }
    }
}

@Composable
private fun SetupOptionCard(
    title: String,
    description: String,
    cta: String,
    tag: String?,
    primary: Boolean,
    onClick: () -> Unit
) {
    val containerColor = if (primary) {
        MaterialTheme.colorScheme.primary.copy(alpha = 0.12f)
    } else {
        MaterialTheme.colorScheme.surfaceVariant
    }
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = containerColor)
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text(
                    text = title,
                    style = MaterialTheme.typography.titleMedium,
                    color = if (primary) MaterialTheme.colorScheme.primary
                    else MaterialTheme.colorScheme.onSurface
                )
                if (tag != null) {
                    Text(
                        text = tag,
                        style = MaterialTheme.typography.labelSmall,
                        color = if (primary) MaterialTheme.colorScheme.primary
                        else MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
            Text(
                text = description,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurface
            )
            if (primary) {
                Button(
                    onClick = onClick,
                    modifier = Modifier.fillMaxWidth()
                ) { Text(cta) }
            } else {
                OutlinedButton(
                    onClick = onClick,
                    modifier = Modifier.fillMaxWidth()
                ) { Text(cta) }
            }
        }
    }
}
