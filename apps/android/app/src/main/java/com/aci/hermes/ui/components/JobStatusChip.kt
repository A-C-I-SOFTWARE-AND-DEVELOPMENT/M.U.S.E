package com.aci.hermes.ui.components

import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.aci.hermes.data.cockpit.JobStatus
import com.aci.hermes.ui.theme.JarvisAmber
import com.aci.hermes.ui.theme.JarvisCrimson
import com.aci.hermes.ui.theme.JarvisCyan
import com.aci.hermes.ui.theme.JarvisGold
import com.aci.hermes.ui.theme.JarvisInkRaised
import com.aci.hermes.ui.theme.JarvisJade
import com.aci.hermes.ui.theme.JarvisSignalDim
import com.aci.hermes.ui.theme.JarvisSignalMute
import com.aci.hermes.ui.theme.JarvisTokens
import com.aci.hermes.ui.theme.JarvisViolet

/**
 * The readable mobile state vocabulary for a job. A coarsening of the wire
 * [JobStatus] superset into the handful of states a user reasons about on a
 * phone, plus [VERIFYING] (a UI-runtime state the Job Detail screen shows
 * while a "run verification" call is in flight — no wire status carries it).
 */
enum class JobUiState(val label: String) {
    QUEUED("Queued"),
    RUNNING("Running"),
    PAUSED("Paused"),
    BLOCKED("Blocked"),
    WAITING_APPROVAL("Waiting for approval"),
    VERIFYING("Verifying"),
    PUBLISHING("Publishing"),
    COMPLETED("Completed"),
    PUBLISHED("Published"),
    FAILED("Failed"),
    CANCELLED("Cancelled"),
    UNKNOWN("Unknown");

    /** Active = still moving; drives faster polling + the "Active" list section. */
    val isActive: Boolean
        get() = this == QUEUED || this == RUNNING || this == PAUSED ||
            this == PUBLISHING || this == VERIFYING

    /** Needs the owner's attention to advance (the "Blocked" list section). */
    val needsAttention: Boolean
        get() = this == BLOCKED || this == WAITING_APPROVAL

    companion object {
        /** Map a wire [JobStatus] (or an unknown string) to the UI vocabulary. */
        fun from(status: JobStatus?): JobUiState = when (status) {
            JobStatus.DRAFT, JobStatus.QUEUED -> QUEUED
            JobStatus.RUNNING, JobStatus.APPROVED -> RUNNING
            JobStatus.PAUSED -> PAUSED
            JobStatus.BLOCKED, JobStatus.DISCONNECTED -> BLOCKED
            JobStatus.WAITING_FOR_APPROVAL -> WAITING_APPROVAL
            JobStatus.PUBLISHING -> PUBLISHING
            JobStatus.COMPLETED -> COMPLETED
            JobStatus.PUBLISHED -> PUBLISHED
            JobStatus.FAILED -> FAILED
            JobStatus.CANCELLED -> CANCELLED
            null -> UNKNOWN
        }

        fun fromWire(wire: String?): JobUiState = from(JobStatus.fromWire(wire))
    }
}

private fun colorFor(state: JobUiState): Color = when (state) {
    JobUiState.RUNNING, JobUiState.PUBLISHING -> JarvisGold
    JobUiState.QUEUED -> JarvisCyan
    JobUiState.PAUSED -> JarvisSignalMute
    JobUiState.BLOCKED -> JarvisCrimson
    JobUiState.WAITING_APPROVAL -> JarvisAmber
    JobUiState.VERIFYING -> JarvisViolet
    JobUiState.COMPLETED, JobUiState.PUBLISHED -> JarvisJade
    JobUiState.FAILED -> JarvisCrimson
    JobUiState.CANCELLED -> JarvisSignalMute
    JobUiState.UNKNOWN -> JarvisSignalMute
}

/**
 * Colour-coded status chip for a job. A dot in the state colour plus the
 * readable [JobUiState.label]. Same visual language as [GatewayStatusPill].
 */
@Composable
fun JobStatusChip(
    state: JobUiState,
    modifier: Modifier = Modifier,
) {
    val accent = colorFor(state)
    Surface(
        shape = JarvisTokens.ShapePill,
        color = JarvisInkRaised,
        modifier = modifier
            .height(JarvisTokens.PillHeight)
            .border(
                width = JarvisTokens.BorderHairline,
                color = accent.copy(alpha = 0.35f),
                shape = JarvisTokens.ShapePill,
            ),
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm),
            modifier = Modifier.padding(horizontal = JarvisTokens.SpaceMd),
        ) {
            Surface(shape = CircleShape, color = accent, modifier = Modifier.size(8.dp), content = {})
            Text(
                text = state.label,
                style = MaterialTheme.typography.labelMedium,
                color = JarvisSignalDim,
            )
        }
    }
}
