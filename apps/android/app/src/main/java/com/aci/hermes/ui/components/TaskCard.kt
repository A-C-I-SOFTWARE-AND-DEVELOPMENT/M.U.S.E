package com.aci.hermes.ui.components

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.AssistChip
import androidx.compose.material3.AssistChipDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.aci.hermes.R
import com.aci.hermes.ui.theme.JarvisCrimson
import com.aci.hermes.ui.theme.JarvisCyan
import com.aci.hermes.ui.theme.JarvisGold
import com.aci.hermes.ui.theme.JarvisInkRaised
import com.aci.hermes.ui.theme.JarvisJade
import com.aci.hermes.ui.theme.JarvisSignal
import com.aci.hermes.ui.theme.JarvisSignalDim
import com.aci.hermes.ui.theme.JarvisSignalMute
import com.aci.hermes.ui.theme.JarvisTokens

enum class TaskCardStatus {
    Drafting, AwaitingApproval, Running, Complete, Blocked;

    @Composable
    fun label(): String = when (this) {
        Drafting -> stringResource(R.string.task_status_drafting)
        AwaitingApproval -> stringResource(R.string.task_status_awaiting_approval)
        Running -> stringResource(R.string.task_status_running)
        Complete -> stringResource(R.string.task_status_complete)
        Blocked -> stringResource(R.string.task_status_blocked)
    }

    internal fun accent(): Color = when (this) {
        Drafting -> JarvisSignalMute
        AwaitingApproval -> JarvisGold
        Running -> JarvisCyan
        Complete -> JarvisJade
        Blocked -> JarvisCrimson
    }
}

/**
 * Generic task card. Title + body + small status chip with a coloured
 * dot mirroring the [TaskCardStatus] tier. Optional primary action row.
 */
@Composable
fun TaskCard(
    title: String,
    description: String?,
    status: TaskCardStatus,
    modifier: Modifier = Modifier,
    onOpen: (() -> Unit)? = null,
    onPrimary: (() -> Unit)? = null,
    primaryLabel: String = stringResource(R.string.orchestrator_open_task),
) {
    CommandCard(
        title = title.ifBlank { stringResource(R.string.orchestrator_untitled_task) },
        subtitle = description?.takeIf { it.isNotBlank() }?.let {
            if (it.length > 160) it.take(160) + "…" else it
        },
        tier = CardTier.INFO,
        leadingDot = false,
        modifier = modifier,
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm),
            modifier = Modifier.fillMaxWidth(),
        ) {
            AssistChip(
                onClick = { onOpen?.invoke() },
                label = {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm),
                    ) {
                        Surface(
                            color = status.accent(),
                            shape = CircleShape,
                            modifier = Modifier.size(8.dp),
                            content = {},
                        )
                        Text(
                            text = status.label(),
                            style = MaterialTheme.typography.labelMedium,
                            color = JarvisSignal,
                        )
                    }
                },
                colors = AssistChipDefaults.assistChipColors(
                    containerColor = JarvisInkRaised,
                    labelColor = JarvisSignalDim,
                ),
            )
            if (onPrimary != null) {
                OutlinedButton(onClick = onPrimary, shape = JarvisTokens.ShapeButton) {
                    Text(primaryLabel)
                }
            }
        }
    }
}
