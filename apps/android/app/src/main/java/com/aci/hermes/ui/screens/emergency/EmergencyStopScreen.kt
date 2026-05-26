package com.aci.hermes.ui.screens.emergency

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
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
import androidx.compose.ui.unit.dp
import com.aci.hermes.R
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun EmergencyStopScreen(viewModel: EmergencyStopViewModel, onBack: () -> Unit) {
    val ui by viewModel.state.collectAsState()
    val es = ui.state
    var reason by remember { mutableStateOf("") }
    var confirmEngage by remember { mutableStateOf(false) }
    var confirmRelease by remember { mutableStateOf(false) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text(stringResource(R.string.emergency_stop_title))
                        Text(
                            stringResource(R.string.emergency_stop_subtitle),
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
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier.fillMaxSize().padding(padding).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Card(
                colors = CardDefaults.cardColors(
                    containerColor = if (es.engaged) MaterialTheme.colorScheme.errorContainer
                                     else MaterialTheme.colorScheme.surfaceVariant,
                ),
                shape = RoundedCornerShape(20.dp),
            ) {
                Column(modifier = Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Surface(
                            color = if (es.engaged) MaterialTheme.colorScheme.error
                                    else MaterialTheme.colorScheme.tertiary,
                            shape = CircleShape,
                            modifier = Modifier.size(14.dp),
                        ) {}
                        Text(
                            text = if (es.engaged) stringResource(R.string.emergency_stop_armed)
                                   else stringResource(R.string.emergency_stop_inactive),
                            style = MaterialTheme.typography.titleMedium,
                            modifier = Modifier.padding(start = 8.dp),
                        )
                    }
                    HorizontalDivider()
                    Text(
                        "${stringResource(R.string.emergency_stop_status_label)}: ${if (es.engaged) "engaged" else "stand by"}",
                        style = MaterialTheme.typography.bodyMedium,
                    )
                    if (es.engaged) {
                        es.reason?.let {
                            Text("${stringResource(R.string.emergency_stop_reason_label)}: $it", style = MaterialTheme.typography.bodyMedium)
                        }
                        es.engagedAt?.let {
                            Text(
                                "${stringResource(R.string.emergency_stop_engaged_at)}: ${formatTs(it)}",
                                style = MaterialTheme.typography.bodySmall,
                            )
                        }
                    }
                }
            }

            if (!es.engaged) {
                OutlinedTextField(
                    value = reason,
                    onValueChange = { reason = it },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("Reason (optional)") },
                )
                Button(
                    onClick = { confirmEngage = true },
                    colors = ButtonDefaults.buttonColors(
                        containerColor = MaterialTheme.colorScheme.error,
                        contentColor = MaterialTheme.colorScheme.onError,
                    ),
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Icon(Icons.Default.Stop, contentDescription = null)
                    Text(stringResource(R.string.emergency_stop_engage), modifier = Modifier.padding(start = 6.dp))
                }
            } else {
                Button(
                    onClick = { confirmRelease = true },
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text(stringResource(R.string.emergency_stop_release))
                }
            }
        }
    }

    if (confirmEngage) {
        AlertDialog(
            onDismissRequest = { confirmEngage = false },
            title = { Text(stringResource(R.string.emergency_stop_confirm_title)) },
            text = { Text(stringResource(R.string.emergency_stop_confirm_body)) },
            confirmButton = {
                TextButton(onClick = {
                    confirmEngage = false
                    viewModel.engage(reason.ifBlank { null })
                }) { Text(stringResource(R.string.emergency_stop_engage_cta)) }
            },
            dismissButton = {
                TextButton(onClick = { confirmEngage = false }) {
                    Text(stringResource(R.string.action_cancel))
                }
            },
        )
    }

    if (confirmRelease) {
        AlertDialog(
            onDismissRequest = { confirmRelease = false },
            title = { Text(stringResource(R.string.emergency_stop_release)) },
            text = { Text(stringResource(R.string.emergency_stop_release_confirm)) },
            confirmButton = {
                TextButton(onClick = {
                    confirmRelease = false
                    viewModel.release()
                }) { Text(stringResource(R.string.emergency_stop_release_cta)) }
            },
            dismissButton = {
                TextButton(onClick = { confirmRelease = false }) {
                    Text(stringResource(R.string.action_cancel))
                }
            },
        )
    }
}

private fun formatTs(ts: Long): String =
    SimpleDateFormat("MMM d • HH:mm:ss", Locale.getDefault()).format(Date(ts))
