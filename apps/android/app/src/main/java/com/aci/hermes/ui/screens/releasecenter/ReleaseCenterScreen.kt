package com.aci.hermes.ui.screens.releasecenter

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
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import com.aci.hermes.data.cockpit.ServerCapabilities
import com.aci.hermes.ui.designsystem.museButton
import com.aci.hermes.ui.designsystem.museButtonVariant
import com.aci.hermes.ui.designsystem.museCard
import com.aci.hermes.ui.designsystem.museChip
import com.aci.hermes.ui.theme.JarvisSignal
import com.aci.hermes.ui.theme.JarvisSignalDim
import com.aci.hermes.ui.theme.JarvisTokens

/**
 * Release / Download Center — honest build, download, signing, and backend
 * facts. No fabricated CI/PR state.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ReleaseCenterScreen(
    viewModel: ReleaseCenterViewModel,
    onBack: () -> Unit,
) {
    val state by viewModel.state.collectAsState()
    val clipboard = LocalClipboardManager.current

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Release & Download") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
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
            SectionCard("This build") {
                Line("Version", viewModel.appVersion)
                Line("Build type", viewModel.buildType)
                Line("Application id", viewModel.applicationId)
            }

            SectionCard("Download & install") {
                Text(
                    "The latest APK is published as a rolling GitHub release, refreshed on " +
                        "every change under apps/android/.",
                    style = MaterialTheme.typography.bodySmall,
                    color = JarvisSignalDim,
                )
                Text(
                    viewModel.downloadUrl,
                    style = MaterialTheme.typography.bodySmall,
                    color = JarvisSignalDim,
                    fontFamily = FontFamily.Monospace,
                )
                museButton(
                    onClick = { clipboard.setText(AnnotatedString(viewModel.downloadUrl)) },
                    text = "Copy download link",
                    variant = museButtonVariant.Secondary,
                )
                Text(
                    "Install: open the link on your phone, download the .apk, tap it, allow " +
                        "installs from this source if prompted. Requires Android 8.0+ (API 26).",
                    style = MaterialTheme.typography.bodySmall,
                    color = JarvisSignalDim,
                )
            }

            SectionCard("Signing") {
                Text(
                    "Release signing is controlled by CI secrets. When they are set, the " +
                        "published APK is properly release-signed; when unset, it falls back to " +
                        "debug signing (still installable; Android may warn \"unknown developer\").",
                    style = MaterialTheme.typography.bodySmall,
                    color = JarvisSignalDim,
                )
                Text("Required secret names (values never shown):", style = MaterialTheme.typography.labelSmall, color = JarvisSignalDim)
                viewModel.signingSecretNames.forEach {
                    Text("• $it", style = MaterialTheme.typography.bodySmall, color = JarvisSignalDim, fontFamily = FontFamily.Monospace)
                }
                Text(
                    "The app can't read CI secret state, so it never claims \"signed\" — confirm " +
                        "in the release workflow / asset label.",
                    style = MaterialTheme.typography.bodySmall,
                    color = JarvisSignalDim,
                )
            }

            BackendCard(state.capabilities, state.backendUnavailable, onRetry = viewModel::refresh)

            SectionCard("Live CI / PR status") {
                Text(
                    "Live CI checks, PR state, and release artifacts need a configured GitHub " +
                        "token, which this build does not wire up. Rather than show a fabricated " +
                        "status, the app links you to the workflow above. (Tracked as a follow-up.)",
                    style = MaterialTheme.typography.bodySmall,
                    color = JarvisSignalDim,
                )
            }
        }
    }
}

@Composable
private fun BackendCard(
    capabilities: ServerCapabilities?,
    unavailable: String?,
    onRetry: () -> Unit,
) {
    SectionCard("Backend") {
        if (capabilities == null) {
            Text(
                "Pair a gateway in Settings to see backend version and capabilities." +
                    (unavailable?.let { " ($it)" } ?: ""),
                style = MaterialTheme.typography.bodySmall,
                color = JarvisSignalDim,
            )
            museButton(onClick = onRetry, text = "Retry", variant = museButtonVariant.Secondary)
        } else {
            Line("Gateway version", capabilities.gatewayVersion.ifBlank { "—" })
            Line("API version", capabilities.apiVersion.ifBlank { "—" })
            Row(horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm)) {
                museChip(label = if (capabilities.executeAllowed) "execute allowed" else "execute blocked")
                museChip(label = if (capabilities.ownerGateRequired) "owner-gated" else "no owner gate")
            }
            if (capabilities.detectedClis.isNotEmpty()) {
                Line("Detected CLIs", capabilities.detectedClis.joinToString(", "))
            }
        }
    }
}

@Composable
private fun SectionCard(title: String, content: @Composable () -> Unit) {
    museCard(modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(JarvisTokens.SpaceLg), verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm)) {
            Text(title, style = MaterialTheme.typography.titleSmall, color = JarvisSignal)
            content()
        }
    }
}

@Composable
private fun Line(label: String, value: String) {
    Row(horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm)) {
        Text("$label:", style = MaterialTheme.typography.bodySmall, color = JarvisSignalDim, fontWeight = FontWeight.SemiBold)
        Text(value, style = MaterialTheme.typography.bodySmall, color = JarvisSignal)
    }
}
