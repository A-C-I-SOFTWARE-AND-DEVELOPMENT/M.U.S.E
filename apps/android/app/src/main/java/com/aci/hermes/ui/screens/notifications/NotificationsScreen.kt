package com.aci.hermes.ui.screens.notifications

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.DeleteSweep
import androidx.compose.material.icons.filled.DoneAll
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.aci.hermes.R
import com.aci.hermes.data.model.JarvisNotification
import com.aci.hermes.data.model.JarvisNotificationKind
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun NotificationsScreen(
    viewModel: NotificationsViewModel,
    onBack: () -> Unit,
    onOpenApprovals: () -> Unit,
) {
    val state by viewModel.state.collectAsState()
    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text(stringResource(R.string.notifications_title))
                        Text(
                            stringResource(R.string.notifications_subtitle),
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = null)
                    }
                },
                actions = {
                    IconButton(onClick = viewModel::markAllRead) {
                        Icon(Icons.Default.DoneAll, contentDescription = stringResource(R.string.notifications_mark_read))
                    }
                    IconButton(onClick = viewModel::clear) {
                        Icon(Icons.Default.DeleteSweep, contentDescription = stringResource(R.string.notifications_clear))
                    }
                },
            )
        },
    ) { padding ->
        if (state.items.isEmpty()) {
            Column(
                modifier = Modifier.fillMaxSize().padding(padding),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center,
            ) { Text(stringResource(R.string.notifications_empty), style = MaterialTheme.typography.bodyMedium) }
        } else {
            LazyColumn(
                modifier = Modifier.fillMaxSize().padding(padding),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                items(state.items) { item ->
                    NotificationRow(
                        item = item,
                        onTap = {
                            viewModel.markRead(item.id)
                            if (item.kind == JarvisNotificationKind.APPROVAL_NEEDED) onOpenApprovals()
                        },
                    )
                }
            }
        }
    }
}

@Composable
private fun NotificationRow(item: JarvisNotification, onTap: () -> Unit) {
    Card(
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
        shape = RoundedCornerShape(12.dp),
        onClick = onTap,
    ) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(12.dp),
            horizontalArrangement = Arrangement.spacedBy(10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            KindDot(item.kind)
            Column(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Text(item.title, style = MaterialTheme.typography.titleSmall)
                Text(item.body, style = MaterialTheme.typography.bodySmall, maxLines = 2)
                Text(
                    text = SimpleDateFormat("MMM d • HH:mm", Locale.getDefault()).format(Date(item.createdAt)),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            if (!item.read) {
                Surface(
                    color = MaterialTheme.colorScheme.primary,
                    shape = androidx.compose.foundation.shape.CircleShape,
                    modifier = Modifier.padding(start = 4.dp).then(Modifier).then(Modifier),
                ) { Text(" ", color = Color.Transparent, modifier = Modifier.padding(4.dp)) }
            }
        }
    }
}

@Composable
private fun KindDot(kind: JarvisNotificationKind) {
    val color = when (kind) {
        JarvisNotificationKind.INFO -> MaterialTheme.colorScheme.secondary
        JarvisNotificationKind.SUCCESS -> MaterialTheme.colorScheme.tertiary
        JarvisNotificationKind.WARNING -> MaterialTheme.colorScheme.primary
        JarvisNotificationKind.APPROVAL_NEEDED -> MaterialTheme.colorScheme.primary
        JarvisNotificationKind.GATEWAY_EVENT -> MaterialTheme.colorScheme.secondary
        JarvisNotificationKind.EMERGENCY -> MaterialTheme.colorScheme.error
    }
    Surface(
        color = color,
        shape = androidx.compose.foundation.shape.CircleShape,
        modifier = Modifier.padding(end = 4.dp),
    ) { Text(" ", color = Color.Transparent, modifier = Modifier.padding(6.dp)) }
}
