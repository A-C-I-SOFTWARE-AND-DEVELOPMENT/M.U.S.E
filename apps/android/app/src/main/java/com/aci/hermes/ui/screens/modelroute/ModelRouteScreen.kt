package com.aci.hermes.ui.screens.modelroute

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.MutableTransitionState
import androidx.compose.animation.fadeIn
import androidx.compose.animation.slideInVertically
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontFamily
import com.aci.hermes.R
import com.aci.hermes.data.cockpit.ModelRouteDecision
import com.aci.hermes.data.cockpit.ModelRoutesSync
import com.aci.hermes.ui.designsystem.museButton
import com.aci.hermes.ui.designsystem.museButtonVariant
import com.aci.hermes.ui.designsystem.museCard
import com.aci.hermes.ui.designsystem.museChip
import com.aci.hermes.ui.designsystem.museEmptyState
import com.aci.hermes.ui.designsystem.museMotion
import com.aci.hermes.ui.designsystem.museSectionHeader
import com.aci.hermes.ui.theme.JarvisTokens

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ModelRouteScreen(viewModel: ModelRouteViewModel, onBack: () -> Unit) {
    val state by viewModel.state.collectAsState()
    var pendingPaid by remember { mutableStateOf<Boolean?>(null) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.model_route_title)) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = null)
                    }
                },
                actions = {
                    IconButton(onClick = viewModel::refresh) {
                        Icon(
                            Icons.Default.Refresh,
                            contentDescription = stringResource(R.string.model_route_refresh),
                        )
                    }
                },
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(JarvisTokens.SpaceLg),
            verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceMd),
        ) {
            Text(
                stringResource(R.string.model_route_subtitle),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            PaidRoutingCard(
                paidEnabled = state.paidEnabled,
                onToggle = { pendingPaid = it },
            )
            state.message?.let { msg ->
                Text(msg, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary)
            }

            if (state.sync is ModelRoutesSync.NotPaired) {
                Box(
                    modifier = Modifier.fillMaxSize(),
                    contentAlignment = Alignment.Center,
                ) {
                    museEmptyState(
                        title = "No gateway paired",
                        body = stringResource(R.string.model_route_not_paired),
                    )
                }
            } else {
                LazyColumn(
                    modifier = Modifier.fillMaxWidth(),
                    verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceMd),
                ) {
                    items(state.routes, key = { it.taskClass }) { decision ->
                        RouteCard(
                            decision = decision,
                            onPin = { model -> viewModel.setOverride(decision.taskClass, model) },
                            onClear = { viewModel.clearOverride(decision.taskClass) },
                        )
                    }
                }
            }
        }
    }

    pendingPaid?.let { target ->
        AuthorizePaidDialog(
            onConfirm = { phrase ->
                viewModel.setPaidEnabled(target, phrase)
                pendingPaid = null
            },
            onDismiss = { pendingPaid = null },
        )
    }
}

@Composable
private fun PaidRoutingCard(paidEnabled: Boolean, onToggle: (Boolean) -> Unit) {
    museCard(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(JarvisTokens.SpaceLg),
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Column(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceXs)) {
                Text(stringResource(R.string.model_route_paid_title), style = MaterialTheme.typography.titleMedium)
                Text(
                    stringResource(R.string.model_route_paid_subtitle),
                    style = MaterialTheme.typography.bodySmall,
                )
            }
            // The switch never flips state directly — it raises the intended
            // target so the screen can demand owner authorization first.
            Switch(checked = paidEnabled, onCheckedChange = { onToggle(!paidEnabled) })
        }
    }
}

@Composable
private fun RouteCard(
    decision: ModelRouteDecision,
    onPin: (String) -> Unit,
    onClear: () -> Unit,
) {
    var pin by remember(decision.taskClass) { mutableStateOf(decision.ownerOverride ?: "") }
    // Subtle entrance: route rows fade + rise in on the standard curve.
    val appear = remember { MutableTransitionState(false).apply { targetState = true } }
    AnimatedVisibility(
        visibleState = appear,
        enter = fadeIn(museMotion.standard()) +
            slideInVertically(museMotion.standard()) { it / 6 },
    ) {
        museCard(modifier = Modifier.fillMaxWidth()) {
            Column(modifier = Modifier.padding(JarvisTokens.SpaceLg), verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm)) {
                museSectionHeader(
                    title = decision.taskClass,
                    trailing = if (decision.localFirst) {
                        { museChip(label = stringResource(R.string.model_route_local_first)) }
                    } else {
                        null
                    },
                )
                LabeledValue(
                    stringResource(R.string.model_route_chosen),
                    decision.chosen?.let { "$it  [${decision.routeTier ?: "?"}]" }
                        ?: stringResource(R.string.model_route_none),
                )
                HorizontalDivider()
                LabeledValue(stringResource(R.string.model_route_why), decision.why)
                if (decision.evidence.isNotEmpty()) {
                    LabeledValue(
                        stringResource(R.string.model_route_evidence),
                        decision.evidence.joinToString("\n") { e ->
                            "• ${e.model}: score=${"%.2f".format(e.score)} (n=${e.samples})"
                        },
                    )
                }

                // Owner override (a reversible preference; pinning is not paid-gated).
                museSectionHeader(title = stringResource(R.string.model_route_owner_override))
                OutlinedTextField(
                    value = pin,
                    onValueChange = { pin = it },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                    placeholder = { Text(stringResource(R.string.model_route_override_hint)) },
                )
                Row(horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm)) {
                    museButton(
                        onClick = { onPin(pin) },
                        text = stringResource(R.string.model_route_override_save),
                        variant = museButtonVariant.Primary,
                        enabled = pin.isNotBlank(),
                    )
                    museButton(
                        onClick = { pin = ""; onClear() },
                        text = stringResource(R.string.model_route_override_clear),
                        variant = museButtonVariant.Secondary,
                        enabled = decision.isOverridden,
                    )
                }
            }
        }
    }
}

@Composable
private fun LabeledValue(label: String, value: String) {
    Column(verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceXxs)) {
        Text(label, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = MaterialTheme.typography.bodyMedium, fontFamily = FontFamily.Monospace)
    }
}

@Composable
private fun AuthorizePaidDialog(onConfirm: (String) -> Unit, onDismiss: () -> Unit) {
    var phrase by remember { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(R.string.model_route_paid_confirm_title)) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm)) {
                Text(stringResource(R.string.model_route_paid_confirm_body))
                Text(
                    "\"${ModelRouteViewModel.OWNER_AUTHORIZATION_PHRASE}\"",
                    style = MaterialTheme.typography.bodySmall,
                    fontFamily = FontFamily.Monospace,
                )
                OutlinedTextField(
                    value = phrase,
                    onValueChange = { phrase = it },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        },
        confirmButton = {
            TextButton(
                onClick = { onConfirm(phrase) },
                enabled = phrase == ModelRouteViewModel.OWNER_AUTHORIZATION_PHRASE,
            ) {
                Text(stringResource(R.string.model_route_paid_confirm_cta))
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text(stringResource(R.string.model_route_cancel)) }
        },
    )
}
