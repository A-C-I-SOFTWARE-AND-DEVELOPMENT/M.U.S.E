package com.aci.hermes.ui.screens.memory

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
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
import androidx.compose.material3.ExperimentalMaterial3Api
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
import com.aci.hermes.ui.designsystem.museCard
import com.aci.hermes.ui.designsystem.museChip
import com.aci.hermes.ui.theme.JarvisTokens
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
    const val INBOX = "memory_inbox"
    const val CONTRADICTIONS = "memory_contradictions"
    const val FRESHNESS = "memory_freshness"
    fun card(id: String) = "memory_card_$id"
    fun filter(name: String) = "memory_filter_$name"
    fun tab(name: String) = "memory_tab_$name"
    fun proposedCard(id: String) = "memory_proposed_$id"
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MemoryScreen(
    viewModel: MemoryViewModel,
    onBack: () -> Unit,
    relatedLoader: (suspend (String) -> com.aci.hermes.data.cockpit.CockpitResult<com.aci.hermes.data.cockpit.RelatedItemList>)? = null,
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
                .padding(horizontal = JarvisTokens.SpaceLg),
            verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceMd),
        ) {
            MemoryTabs(
                active = state.tab,
                inboxCount = state.proposed.size,
                conflictCount = state.contradictions.size,
                onSelect = viewModel::selectTab,
            )
            when (state.tab) {
                MemoryTab.STORED -> {
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
                            verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm),
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
                MemoryTab.INBOX -> ProposedInboxSection(
                    proposed = state.proposed,
                    sync = state.treeSync,
                    onApprove = viewModel::approveProposed,
                    onReject = { id -> viewModel.rejectProposed(id) },
                )
                MemoryTab.CONTRADICTIONS -> ContradictionsSection(
                    contradictions = state.contradictions,
                    onResolve = { id, winnerId -> viewModel.resolveContradiction(id, winnerId) },
                )
                MemoryTab.FRESHNESS -> FreshnessSection(
                    nodes = state.freshness,
                )
            }
        }
    }

    state.selectedItem?.let { item ->
        MemoryDetail(
            item = item,
            onDismiss = viewModel::closeDetail,
            onCorrect = { viewModel.beginCorrect(item) },
            onDelete = { viewModel.beginDelete(item) },
            relatedLoader = relatedLoader,
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

@Composable
fun MemoryFilter(
    active: MemoryCategory?,
    onSelect: (MemoryCategory?) -> Unit,
) {
    LazyRow(horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm)) {
        item {
            museChip(
                label = stringResource(R.string.memory_filter_all),
                selected = active == null,
                onClick = { onSelect(null) },
                modifier = Modifier.testTag(MemoryScreenTags.filter("ALL")),
            )
        }
        items(MemoryCategory.values().toList()) { cat ->
            museChip(
                label = cat.display,
                selected = active == cat,
                onClick = { onSelect(cat) },
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

@Composable
fun MemoryCard(
    item: MemoryItem,
    onOpen: () -> Unit,
    onCorrect: () -> Unit,
    onDelete: () -> Unit,
) {
    museCard(
        modifier = Modifier
            .fillMaxWidth()
            .testTag(MemoryScreenTags.card(item.id))
            .clickable(onClick = onOpen),
    ) {
        Column(
            modifier = Modifier.padding(JarvisTokens.SpaceLg),
            verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                CategoryPill(item.category)
                if (item.redacted) {
                    Surface(
                        modifier = Modifier
                            .padding(start = JarvisTokens.SpaceSm)
                            .clip(RoundedCornerShape(50)),
                        color = MaterialTheme.colorScheme.errorContainer,
                    ) {
                        Row(
                            modifier = Modifier.padding(horizontal = JarvisTokens.SpaceSm, vertical = JarvisTokens.SpaceXxs),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceXs),
                        ) {
                            Icon(Icons.Default.Lock, contentDescription = null, modifier = Modifier.padding(end = JarvisTokens.SpaceXxs))
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
            Row(horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceXs)) {
                museChip(label = item.durability.display, onClick = onOpen)
                museChip(label = item.confidence.display, onClick = onOpen)
            }
            HorizontalDivider()
            Row(horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm)) {
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
            .padding(horizontal = 10.dp, vertical = JarvisTokens.SpaceXs),
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
