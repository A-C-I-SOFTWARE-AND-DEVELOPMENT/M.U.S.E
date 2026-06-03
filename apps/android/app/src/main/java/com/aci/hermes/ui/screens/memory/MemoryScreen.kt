package com.aci.hermes.ui.screens.memory

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Clear
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.AssistChip
import androidx.compose.material3.AssistChipDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.aci.hermes.R
import com.aci.hermes.data.memory.MemoryCategory
import com.aci.hermes.data.memory.MemoryItem
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

object MemoryScreenTags {
    const val ROOT = "memory_screen"
    const val SEARCH = "memory_search"
    const val LIST = "memory_list"
    const val EMPTY = "memory_empty"
    const val DETAIL = "memory_detail"
    const val CORRECT_DIALOG = "memory_correct_dialog"
    const val DELETE_DIALOG = "memory_delete_dialog"
    fun card(id: String) = "memory_card_$id"
    fun filter(name: String) = "memory_filter_$name"
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MemoryScreen(
    viewModel: MemoryViewModel,
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
        modifier = Modifier.testTag(MemoryScreenTags.ROOT),
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.memory_title)) },
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
                .padding(padding)
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            MemorySearch(
                query = state.query,
                onQueryChange = viewModel::setQuery,
            )
            MemoryFilter(
                active = state.activeCategory,
                onSelect = viewModel::setCategory,
            )
            HeaderRow(total = state.allItems.size, shown = state.visibleItems.size)
            if (state.visibleItems.isEmpty()) {
                EmptyState()
            } else {
                LazyColumn(
                    modifier = Modifier
                        .fillMaxSize()
                        .testTag(MemoryScreenTags.LIST),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    items(state.visibleItems, key = { it.id }) { item ->
                        if (item.category == MemoryCategory.SOCIAL_SPEECH_PATTERN) {
                            Box(modifier = Modifier.testTag(MemoryScreenTags.card(item.id))) {
                                SocialPatternCard(
                                    pattern = SocialPatternProjection.from(item),
                                    onTap = { viewModel.open(item) },
                                )
                            }
                        } else {
                            MemoryCard(
                                item = item,
                                onOpen = { viewModel.open(item) },
                                onCorrect = { viewModel.beginCorrect(item) },
                                onDelete = { viewModel.beginDelete(item) },
                            )
                        }
                    }
                }
            }
        }
    }

    state.selectedItem?.let { item ->
        MemoryDetail(
            item = item,
            onDismiss = viewModel::closeDetail,
            onCorrect = { viewModel.beginCorrect(item) },
            onDelete = { viewModel.beginDelete(item) },
        )
    }
    state.correctingItem?.let { item ->
        CorrectMemoryDialog(
            item = item,
            onDismiss = viewModel::cancelCorrect,
            onConfirm = { newContent, reason -> viewModel.confirmCorrect(newContent, reason) },
        )
    }
    state.deletingItem?.let { item ->
        DeleteMemoryDialog(
            item = item,
            onDismiss = viewModel::cancelDelete,
            onConfirm = { reason -> viewModel.confirmDelete(reason) },
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MemorySearch(
    query: String,
    onQueryChange: (String) -> Unit,
) {
    OutlinedTextField(
        value = query,
        onValueChange = onQueryChange,
        modifier = Modifier
            .fillMaxWidth()
            .testTag(MemoryScreenTags.SEARCH),
        singleLine = true,
        leadingIcon = { Icon(Icons.Default.Search, contentDescription = null) },
        trailingIcon = {
            if (query.isNotEmpty()) {
                IconButton(onClick = { onQueryChange("") }) {
                    Icon(Icons.Default.Clear, contentDescription = stringResource(R.string.action_clear))
                }
            }
        },
        placeholder = { Text(stringResource(R.string.memory_search_hint)) },
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MemoryFilter(
    active: MemoryCategory?,
    onSelect: (MemoryCategory?) -> Unit,
) {
    LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        item {
            FilterChip(
                selected = active == null,
                onClick = { onSelect(null) },
                label = { Text(stringResource(R.string.memory_filter_all)) },
                modifier = Modifier.testTag(MemoryScreenTags.filter("ALL")),
            )
        }
        items(MemoryCategory.values().toList()) { cat ->
            FilterChip(
                selected = active == cat,
                onClick = { onSelect(cat) },
                label = { Text(cat.display) },
                modifier = Modifier.testTag(MemoryScreenTags.filter(cat.name)),
            )
        }
    }
}

@Composable
private fun HeaderRow(total: Int, shown: Int) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Text(
            text = stringResource(R.string.memory_visible_count, shown, total),
            style = MaterialTheme.typography.labelMedium,
        )
        Text(
            text = stringResource(R.string.memory_secrets_redacted),
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.primary,
        )
    }
}

@Composable
private fun EmptyState() {
    com.aci.hermes.ui.components.EmptyState(
        icon = Icons.Default.Search,
        title = stringResource(R.string.memory_empty_filter),
        modifier = Modifier.testTag(MemoryScreenTags.EMPTY),
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MemoryCard(
    item: MemoryItem,
    onOpen: () -> Unit,
    onCorrect: () -> Unit,
    onDelete: () -> Unit,
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .testTag(MemoryScreenTags.card(item.id)),
        onClick = onOpen,
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                CategoryPill(item.category)
                if (item.redacted) {
                    Surface(
                        modifier = Modifier
                            .padding(start = 8.dp)
                            .clip(RoundedCornerShape(50)),
                        color = MaterialTheme.colorScheme.errorContainer,
                    ) {
                        Row(
                            modifier = Modifier.padding(horizontal = 8.dp, vertical = 2.dp),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(4.dp),
                        ) {
                            Icon(Icons.Default.Lock, contentDescription = null, modifier = Modifier.padding(end = 2.dp))
                            Text(stringResource(R.string.memory_redacted_badge), style = MaterialTheme.typography.labelSmall)
                        }
                    }
                }
            }
            Text(
                text = item.title.ifBlank { stringResource(R.string.memory_untitled) },
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
            )
            Text(
                text = item.content.take(180) + if (item.content.length > 180) "…" else "",
                style = MaterialTheme.typography.bodyMedium,
            )
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                AssistChip(
                    onClick = onOpen,
                    label = { Text(item.durability.display) },
                    colors = AssistChipDefaults.assistChipColors(),
                )
                AssistChip(
                    onClick = onOpen,
                    label = { Text(item.confidence.display) },
                )
            }
            HorizontalDivider()
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                IconButton(onClick = onCorrect) {
                    Icon(Icons.Default.Edit, contentDescription = stringResource(R.string.memory_correct_cd))
                }
                IconButton(onClick = onDelete) {
                    Icon(Icons.Default.Delete, contentDescription = stringResource(R.string.memory_delete_cd))
                }
            }
        }
    }
}

@Composable
private fun CategoryPill(category: MemoryCategory) {
    val container = when (category) {
        MemoryCategory.OWNER_PREFERENCE -> MaterialTheme.colorScheme.primaryContainer
        MemoryCategory.PROJECT_MEMORY -> MaterialTheme.colorScheme.secondaryContainer
        MemoryCategory.WORKFLOW_LESSON -> MaterialTheme.colorScheme.tertiaryContainer
        MemoryCategory.TASK_CONTEXT -> MaterialTheme.colorScheme.surfaceVariant
        MemoryCategory.DECISION_RECORD -> MaterialTheme.colorScheme.primaryContainer
        MemoryCategory.SOCIAL_SPEECH_PATTERN -> MaterialTheme.colorScheme.secondaryContainer
        MemoryCategory.SESSION_MEMORY -> MaterialTheme.colorScheme.surface
        MemoryCategory.UNCATEGORIZED -> MaterialTheme.colorScheme.surfaceVariant
    }
    Box(
        modifier = Modifier
            .clip(RoundedCornerShape(50))
            .background(container)
            .padding(horizontal = 10.dp, vertical = 4.dp),
    ) {
        Text(
            text = category.display,
            style = MaterialTheme.typography.labelMedium,
        )
    }
}

internal fun formatTimestamp(ts: Long?): String {
    if (ts == null) return "never"
    val fmt = SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.US)
    return fmt.format(Date(ts))
}
