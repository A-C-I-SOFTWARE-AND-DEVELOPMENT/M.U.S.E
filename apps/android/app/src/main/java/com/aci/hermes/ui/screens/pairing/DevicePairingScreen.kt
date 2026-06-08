package com.aci.hermes.ui.screens.pairing

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontFamily
import com.aci.hermes.R
import com.aci.hermes.data.cockpit.DevicePairingClient
import com.aci.hermes.ui.designsystem.MuseButton
import com.aci.hermes.ui.designsystem.MuseButtonVariant
import com.aci.hermes.ui.designsystem.MuseCard
import com.aci.hermes.ui.theme.JarvisCrimson
import com.aci.hermes.ui.theme.JarvisSignal
import com.aci.hermes.ui.theme.JarvisSignalDim
import com.aci.hermes.ui.theme.JarvisTokens

/**
 * Owner-gated device-pairing flow: request a short-lived code from the gateway,
 * read it back (with the exact owner authorization phrase) and exchange it for
 * the per-device token, which the [DevicePairingViewModel]'s client persists on
 * success. A full-screen push that owns its own top bar — mirrors
 * [com.aci.hermes.ui.screens.modelroute.ModelRouteScreen] for structure
 * (Scaffold + TopAppBar back arrow, `collectAsState`, Card sections).
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DevicePairingScreen(viewModel: DevicePairingViewModel, onBack: () -> Unit) {
    val state by viewModel.state.collectAsState()
    val isSubmitting by viewModel.isSubmitting.collectAsState()
    var deviceName by remember { mutableStateOf("") }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Pair a device") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(
                            Icons.AutoMirrored.Filled.ArrowBack,
                            contentDescription = stringResource(R.string.action_back),
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
                .padding(JarvisTokens.SpaceLg)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceMd),
        ) {
            Text(
                "Pair this device with your Jarvis gateway. Request a code, then " +
                    "confirm it with the owner authorization phrase to receive a " +
                    "per-device token.",
                style = MaterialTheme.typography.bodyMedium,
                color = JarvisSignalDim,
            )

            when (val current = state) {
                is DevicePairingState.Idle -> IdleCard(
                    deviceName = deviceName,
                    onDeviceNameChange = { deviceName = it },
                    onRequestCode = { viewModel.startPairing(deviceName) },
                    submitting = isSubmitting,
                )

                is DevicePairingState.CodeRequested -> CodeRequestedCard(
                    state = current,
                    onConfirm = { code, authorization ->
                        viewModel.confirmPairing(code, authorization)
                    },
                    onCancel = viewModel::reset,
                    submitting = isSubmitting,
                )

                is DevicePairingState.Paired -> PairedCard(
                    state = current,
                    onDone = viewModel::reset,
                )

                is DevicePairingState.Error -> ErrorCard(
                    state = current,
                    onRetry = viewModel::reset,
                )
            }
        }
    }
}

@Composable
private fun IdleCard(
    deviceName: String,
    onDeviceNameChange: (String) -> Unit,
    onRequestCode: () -> Unit,
    submitting: Boolean,
) {
    PairingCard {
        Text("Request a pairing code", style = MaterialTheme.typography.titleMedium, color = JarvisSignal)
        OutlinedTextField(
            value = deviceName,
            onValueChange = onDeviceNameChange,
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
            label = { Text("Device name (optional)") },
        )
        MuseButton(
            onClick = onRequestCode,
            text = "Request code",
            variant = MuseButtonVariant.Primary,
            enabled = !submitting,
            modifier = Modifier.fillMaxWidth(),
        )
    }
}

@Composable
private fun CodeRequestedCard(
    state: DevicePairingState.CodeRequested,
    onConfirm: (code: String, authorization: String) -> Unit,
    onCancel: () -> Unit,
    submitting: Boolean,
) {
    // Pre-fill the issued code; the owner still has to type the authorization
    // phrase, which is what the gateway actually gates token issuance on.
    var code by remember(state.start.pairingCode) { mutableStateOf(state.start.pairingCode) }
    var authorization by remember { mutableStateOf("") }

    PairingCard {
        Text("Confirm pairing", style = MaterialTheme.typography.titleMedium, color = JarvisSignal)
        LabeledValue("Pairing code", state.start.pairingCode)
        if (state.start.expiresIn > 0) {
            LabeledValue("Expires in", "${state.start.expiresIn}s")
        }
        HorizontalDivider()
        OutlinedTextField(
            value = code,
            onValueChange = { code = it },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
            label = { Text("Pairing code") },
        )
        Text(
            "Owner authorization phrase — type it exactly:",
            style = MaterialTheme.typography.titleSmall,
            color = JarvisSignal,
        )
        Text(
            "\"${DevicePairingClient.OWNER_AUTHORIZATION_PHRASE}\"",
            style = MaterialTheme.typography.bodySmall,
            color = JarvisSignalDim,
            fontFamily = FontFamily.Monospace,
        )
        OutlinedTextField(
            value = authorization,
            onValueChange = { authorization = it },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
            label = { Text("Authorization phrase") },
        )
        Row(horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm)) {
            MuseButton(
                onClick = { onConfirm(code, authorization) },
                text = "Confirm",
                variant = MuseButtonVariant.Approve,
                enabled = !submitting &&
                    code.isNotBlank() &&
                    authorization == DevicePairingClient.OWNER_AUTHORIZATION_PHRASE,
            )
            MuseButton(
                onClick = onCancel,
                text = stringResource(R.string.action_cancel),
                variant = MuseButtonVariant.Secondary,
            )
        }
    }
}

@Composable
private fun PairedCard(state: DevicePairingState.Paired, onDone: () -> Unit) {
    PairingCard {
        Text(
            "Device paired",
            style = MaterialTheme.typography.titleMedium,
            color = JarvisSignal,
        )
        LabeledValue("Device id", state.confirm.deviceId)
        LabeledValue("Token type", state.confirm.tokenType)
        Text(
            "The per-device token is stored securely on this device.",
            style = MaterialTheme.typography.bodySmall,
            color = JarvisSignalDim,
        )
        MuseButton(
            onClick = onDone,
            text = stringResource(R.string.action_ok),
            variant = MuseButtonVariant.Primary,
            modifier = Modifier.fillMaxWidth(),
        )
    }
}

@Composable
private fun ErrorCard(state: DevicePairingState.Error, onRetry: () -> Unit) {
    PairingCard {
        Text(
            "Pairing failed",
            style = MaterialTheme.typography.titleMedium,
            color = JarvisCrimson,
        )
        Text(state.message, style = MaterialTheme.typography.bodyMedium, color = JarvisSignalDim)
        if (state.retryable) {
            MuseButton(
                onClick = onRetry,
                text = "Try again",
                variant = MuseButtonVariant.Secondary,
                modifier = Modifier.fillMaxWidth(),
            )
        }
    }
}

@Composable
private fun PairingCard(content: @Composable () -> Unit) {
    MuseCard {
        Column(modifier = Modifier.padding(JarvisTokens.SpaceLg), verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm)) {
            content()
        }
    }
}

@Composable
private fun LabeledValue(label: String, value: String) {
    Column(verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceXxs)) {
        Text(label, style = MaterialTheme.typography.labelMedium, color = JarvisSignalDim)
        Text(value, style = MaterialTheme.typography.bodyMedium, color = JarvisSignal, fontFamily = FontFamily.Monospace)
    }
}
