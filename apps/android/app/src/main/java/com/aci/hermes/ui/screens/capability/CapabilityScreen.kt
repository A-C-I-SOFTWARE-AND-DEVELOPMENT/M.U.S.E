package com.aci.hermes.ui.screens.capability

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import com.aci.hermes.R
import com.aci.hermes.data.capability.RoutePreview
import com.aci.hermes.data.cockpit.CockpitSkill
import com.aci.hermes.data.model.Capability
import com.aci.hermes.data.model.CapabilityCategory

@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun CapabilityScreen(
    viewModel: CapabilityViewModel,
    onBack: () -> Unit,
) {
    val state by viewModel.state.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }

    LaunchedEffect(state.snackbar) {
        state.snackbar?.let {
            snackbarHostState.showSnackbar(it)
            viewModel.consumeSnackbar()
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.capability_title)) },
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
        snackbarHost = { SnackbarHost(snackbarHostState) },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
        ) {
            HeaderBlurb()
            InstalledSkillsCard(sync = state.installedSync, skills = state.installedSkills)
            SearchField(
                query = state.query,
                onQueryChange = viewModel::setQuery,
            )
            CategoryFilters(
                selected = state.category,
                onSelect = viewModel::setCategory,
            )
            AdvancedToggle(
                checked = state.includeAdvanced,
                onCheckedChange = viewModel::setIncludeAdvanced,
                visibleCount = state.results.size,
                totalCount = state.totalCount,
            )
            HorizontalDivider()
            CapabilityList(
                capabilities = state.results,
                onTap = viewModel::select,
            )
        }
    }

    state.selected?.let { capability ->
        val preview = state.preview
        if (preview != null) {
            InvocationSheet(
                capability = capability,
                preview = preview,
                onDismiss = { viewModel.select(null) },
                onStage = { viewModel.stagePromptToClipboard() },
            )
        }
    }
}

/**
 * Live "installed on gateway" skills, alongside the curated catalog. Only
 * shown once a paired gateway has reported real skills; honest about an
 * unreachable gateway, never fabricating entries.
 */
@Composable
private fun InstalledSkillsCard(sync: InstalledSkillsSync, skills: List<CockpitSkill>) {
    // Nothing to show before pairing — keep the screen clean (catalog still works).
    if (sync is InstalledSkillsSync.Idle || sync is InstalledSkillsSync.NotPaired) return
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 4.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(
                stringResource(R.string.capability_installed_title),
                style = MaterialTheme.typography.titleSmall,
                color = MaterialTheme.colorScheme.primary,
            )
            when (sync) {
                is InstalledSkillsSync.Error ->
                    Text(sync.message, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
                is InstalledSkillsSync.Loaded -> {
                    if (skills.isEmpty()) {
                        Text(stringResource(R.string.capability_installed_empty), style = MaterialTheme.typography.bodySmall)
                    } else {
                        skills.forEach { skill ->
                            Text(
                                text = skill.command.ifBlank { "/" + skill.id } +
                                    (skill.name.takeIf { it.isNotBlank() }?.let { " — $it" } ?: ""),
                                style = MaterialTheme.typography.bodySmall,
                            )
                        }
                    }
                }
                else -> Unit
            }
        }
    }
}

@Composable
private fun HeaderBlurb() {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 8.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant,
        ),
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Text(
                text = stringResource(R.string.capability_header_title),
                style = MaterialTheme.typography.titleSmall,
                color = MaterialTheme.colorScheme.primary,
            )
            Text(
                text = stringResource(R.string.capability_header_body),
                style = MaterialTheme.typography.bodySmall,
            )
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun SearchField(
    query: String,
    onQueryChange: (String) -> Unit,
) {
    OutlinedTextField(
        value = query,
        onValueChange = onQueryChange,
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 4.dp)
            .semantics { contentDescription = "Capability search field" },
        leadingIcon = {
            Icon(Icons.Default.Search, contentDescription = null)
        },
        trailingIcon = {
            if (query.isNotEmpty()) {
                IconButton(onClick = { onQueryChange("") }) {
                    Icon(Icons.Default.Close, contentDescription = "Clear search")
                }
            }
        },
        singleLine = true,
        placeholder = { Text(stringResource(R.string.capability_search_hint)) },
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun CategoryFilters(
    selected: CapabilityCategory?,
    onSelect: (CapabilityCategory?) -> Unit,
) {
    val scrollState = rememberScrollState()
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .horizontalScroll(scrollState)
            .padding(horizontal = 16.dp, vertical = 4.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        FilterChip(
            selected = selected == null,
            onClick = { onSelect(null) },
            label = { Text(stringResource(R.string.capability_filter_all)) },
        )
        CapabilityCategory.values().forEach { cat ->
            FilterChip(
                selected = selected == cat,
                onClick = { onSelect(cat) },
                label = { Text(cat.displayName) },
                colors = FilterChipDefaults.filterChipColors(),
            )
        }
    }
}

@Composable
private fun AdvancedToggle(
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit,
    visibleCount: Int,
    totalCount: Int,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(
                stringResource(R.string.capability_advanced_label),
                style = MaterialTheme.typography.bodyLarge,
            )
            Text(
                text = stringResource(
                    R.string.capability_count_template,
                    visibleCount,
                    totalCount,
                ),
                style = MaterialTheme.typography.bodySmall,
            )
        }
        Switch(
            checked = checked,
            onCheckedChange = onCheckedChange,
            modifier = Modifier.semantics { contentDescription = "Show advanced capabilities" },
        )
    }
}

@Composable
private fun CapabilityList(
    capabilities: List<Capability>,
    onTap: (Capability) -> Unit,
) {
    if (capabilities.isEmpty()) {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(24.dp),
            contentAlignment = Alignment.Center,
        ) {
            Text(
                stringResource(R.string.capability_empty),
                style = MaterialTheme.typography.bodyMedium,
            )
        }
        return
    }
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        items(capabilities, key = { it.id }) { cap ->
            SkillCard(capability = cap, onClick = { onTap(cap) })
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
private fun InvocationSheet(
    capability: Capability,
    preview: RoutePreview,
    onDismiss: () -> Unit,
    onStage: () -> Unit,
) {
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = sheetState,
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 24.dp, vertical = 8.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(capability.name, style = MaterialTheme.typography.titleLarge)
            Text(capability.summary, style = MaterialTheme.typography.bodyMedium)

            HorizontalDivider()
            Text(
                stringResource(R.string.capability_route_title),
                style = MaterialTheme.typography.titleSmall,
                color = MaterialTheme.colorScheme.primary,
            )
            preview.lines.forEach { line ->
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                ) {
                    Text(line.label, style = MaterialTheme.typography.bodyMedium)
                    Text(line.value, style = MaterialTheme.typography.bodyMedium)
                }
            }
            preview.note?.let {
                Text(
                    text = it,
                    style = MaterialTheme.typography.bodySmall,
                )
            }

            if (preview.ownerGated) {
                OwnerGatedBanner()
            }

            HorizontalDivider()
            Text(
                stringResource(R.string.capability_prompt_title),
                style = MaterialTheme.typography.titleSmall,
                color = MaterialTheme.colorScheme.primary,
            )
            Card(
                colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.surface,
                ),
            ) {
                Text(
                    text = preview.staged,
                    modifier = Modifier.padding(12.dp),
                    style = MaterialTheme.typography.bodySmall.copy(fontFamily = FontFamily.Monospace),
                )
            }
            Text(
                text = stringResource(R.string.capability_safe_invoke_note),
                style = MaterialTheme.typography.bodySmall,
            )

            FlowRow(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = 8.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Button(onClick = onStage) {
                    Text(stringResource(R.string.capability_stage_prompt))
                }
                OutlinedButton(onClick = onDismiss) {
                    Text(stringResource(R.string.action_close))
                }
            }
        }
    }
}

@Composable
private fun OwnerGatedBanner() {
    Card(
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.errorContainer,
        ),
        modifier = Modifier
            .fillMaxWidth()
            .semantics { contentDescription = "Owner-gated warning" },
    ) {
        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(
                text = stringResource(R.string.capability_owner_gated_title),
                style = MaterialTheme.typography.titleSmall,
                color = MaterialTheme.colorScheme.onErrorContainer,
            )
            Text(
                text = stringResource(R.string.capability_owner_gated_body),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onErrorContainer,
            )
        }
    }
}
