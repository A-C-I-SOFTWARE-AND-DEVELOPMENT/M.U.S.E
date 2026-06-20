package com.aci.hermes.ui.screens.model

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.MutableTransitionState
import androidx.compose.animation.fadeIn
import androidx.compose.animation.slideInVertically
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import com.aci.hermes.data.cockpit.LocalModelEntry
import com.aci.hermes.data.model.LocalModelLabels
import com.aci.hermes.ui.designsystem.museButton
import com.aci.hermes.ui.designsystem.museButtonVariant
import com.aci.hermes.ui.designsystem.museCard
import com.aci.hermes.ui.designsystem.museChip
import com.aci.hermes.ui.designsystem.museEmptyState
import com.aci.hermes.ui.designsystem.museMotion
import com.aci.hermes.ui.designsystem.museSectionHeader
import com.aci.hermes.ui.theme.JarvisTokens

/**
 * Model Center — local Gemma/Ollama status with the honest label vocabulary
 * and an explicit smoke test. Never shows "ready" without evidence; degrades
 * to a clear hint when the backend is unreachable/unpaired.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ModelCenterScreen(
    viewModel: ModelCenterViewModel,
    onBack: () -> Unit,
) {
    val state by viewModel.state.collectAsState()
    val snackbar = remember { SnackbarHostState() }

    LaunchedEffect(state.message) {
        state.message?.let {
            snackbar.showSnackbar(it)
            viewModel.clearMessage()
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Model Center") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
            )
        },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { padding ->
        val status = state.status
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = JarvisTokens.SpaceLg),
            verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm),
            contentPadding = androidx.compose.foundation.layout.PaddingValues(vertical = JarvisTokens.SpaceLg),
        ) {
            if (state.unavailable != null) {
                item { UnavailableCard(state.unavailable!!) }
            }

            if (status != null) {
                item { RuntimeCard(status.runtimeStatus, status.ollamaBase, status.reachError) }

                item {
                    museSectionHeader(
                        title = "Installed models",
                        modifier = Modifier.padding(top = JarvisTokens.SpaceXs),
                    )
                }
                if (status.installed.isEmpty()) {
                    item {
                        museEmptyState(
                            title = "No installed models",
                            body = if (status.reachable) {
                                "No Gemma/Ollama models installed. See Gemma local mode docs to pull one."
                            } else {
                                "Runtime not reachable — install Ollama and a Gemma variant on your backend."
                            },
                        )
                    }
                } else {
                    items(status.installed, key = { it.name }) { entry ->
                        ModelCard(
                            entry = entry,
                            smokeTested = entry.name in state.smokeTested,
                            smokeFailedReason = state.smokeFailed[entry.name],
                            busy = state.busyModel == entry.name,
                            onSmoke = { viewModel.smoke(entry.name) },
                        )
                    }
                }

                if (status.promotions.isNotEmpty()) {
                    item {
                        museSectionHeader(
                            title = "Route by task (local tier)",
                            modifier = Modifier.padding(top = JarvisTokens.SpaceSm),
                        )
                    }
                    item { PromotionsCard(status.promotions) }
                }

                item { RuntimesCard(status) }
            }
        }
    }
}

@Composable
private fun UnavailableCard(message: String) {
    museCard(modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(JarvisTokens.SpaceLg), verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceXs)) {
            Text("Backend unavailable", style = MaterialTheme.typography.titleSmall)
            Text(
                "Pair a gateway in Settings to see local model status. ($message)",
                style = MaterialTheme.typography.bodySmall,
            )
        }
    }
}

@Composable
private fun RuntimeCard(runtimeStatus: String, base: String, reachError: String?) {
    museCard(modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(JarvisTokens.SpaceLg), verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm)) {
            Text("Local runtime", style = MaterialTheme.typography.labelMedium)
            museChip(label = LocalModelLabels.runtime(runtimeStatus))
            Text("Ollama: $base", style = MaterialTheme.typography.bodySmall, fontFamily = FontFamily.Monospace)
            reachError?.takeIf { it.isNotBlank() }?.let {
                Text("Reach error: $it", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
            }
        }
    }
}

@Composable
private fun ModelCard(
    entry: LocalModelEntry,
    smokeTested: Boolean,
    smokeFailedReason: String?,
    busy: Boolean,
    onSmoke: () -> Unit,
) {
    // Subtle entrance: model rows fade + rise in on the standard curve.
    val appear = remember { MutableTransitionState(false).apply { targetState = true } }
    AnimatedVisibility(
        visibleState = appear,
        enter = fadeIn(museMotion.standard()) +
            slideInVertically(museMotion.standard()) { it / 6 },
    ) {
        museCard(modifier = Modifier.fillMaxWidth()) {
            Column(Modifier.padding(JarvisTokens.SpaceLg), verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm)) {
                Text(entry.name, style = MaterialTheme.typography.titleSmall, fontFamily = FontFamily.Monospace)
                museChip(
                    label = LocalModelLabels.model(entry.status, smokeTested, smokeFailedReason != null),
                )
                if (entry.promotedFor.isNotEmpty()) {
                    Text("Promoted for: ${entry.promotedFor.joinToString(", ")}", style = MaterialTheme.typography.bodySmall)
                }
                if (entry.fallbackFor.isNotEmpty()) {
                    Text("Fallback for: ${entry.fallbackFor.joinToString(", ")}", style = MaterialTheme.typography.bodySmall)
                }
                smokeFailedReason?.let {
                    Text("Smoke failed: $it", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
                }
                museButton(
                    onClick = onSmoke,
                    text = if (busy) "Running smoke test…" else "Run smoke test",
                    variant = museButtonVariant.Secondary,
                    enabled = !busy,
                )
            }
        }
    }
}

@Composable
private fun PromotionsCard(promotions: Map<String, String>) {
    museCard(modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(JarvisTokens.SpaceLg), verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceXs)) {
            promotions.forEach { (task, model) ->
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    Text(task, style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.SemiBold)
                    Text(model, style = MaterialTheme.typography.bodySmall, fontFamily = FontFamily.Monospace)
                }
            }
        }
    }
}

@Composable
private fun RuntimesCard(status: com.aci.hermes.data.cockpit.LocalModelsStatus) {
    if (status.runtimes.isEmpty()) return
    museCard(modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(JarvisTokens.SpaceLg), verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceXs)) {
            Text("Detected runtimes", style = MaterialTheme.typography.labelMedium)
            status.runtimes.forEach { rt ->
                Text(
                    "${rt.name}: ${if (rt.available) "present" else "not found"}",
                    style = MaterialTheme.typography.bodySmall,
                )
            }
        }
    }
}
