package com.aci.hermes.ui.designsystem

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.unit.dp
import com.aci.hermes.ui.theme.JarvisCrimson
import com.aci.hermes.ui.theme.JarvisCyan
import com.aci.hermes.ui.theme.JarvisGold
import com.aci.hermes.ui.theme.JarvisInkEdge
import com.aci.hermes.ui.theme.JarvisSignal
import com.aci.hermes.ui.theme.JarvisSignalMute

/** State of a single job phase node on a [musePhaseRail]. */
enum class musePhaseState {
    /** Completed step — drawn as a [JarvisCyan] ring (ring-1). */
    Done,

    /** The step in progress — the white [core][JarvisGold] (filled + bloom). */
    Current,

    /** A failed step — [JarvisCrimson] (danger). */
    Failed,

    /** Not yet reached — a muted hollow node. */
    Pending,
}

/** One labelled node on the rail. */
data class musePhase(
    val label: String,
    val state: musePhaseState,
)

/**
 * A horizontal job-phase rail — the "where is this job" tell for orchestrated
 * work. Each [phase][musePhase] is a node connected by a bar; the bar leading
 * *into* a node is "lit" (cyan) once that node is reached, so progress reads
 * left-to-right.
 *
 * Node semantics: done = cyan ring, current = white core (with a tight bloom),
 * failed = danger, pending = muted hollow. Labels sit under each node.
 *
 * @param phases the ordered steps. Two or more is the useful case.
 */
@Composable
fun musePhaseRail(
    phases: List<musePhase>,
    modifier: Modifier = Modifier,
) {
    if (phases.isEmpty()) return

    Column(modifier = modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            phases.forEachIndexed { index, phase ->
                // The connecting bar BEFORE this node (skip before the first).
                if (index > 0) {
                    val prevReached = phases[index - 1].state != musePhaseState.Pending
                    PhaseConnector(
                        lit = prevReached,
                        modifier = Modifier.weight(1f),
                    )
                }
                PhaseNode(state = phase.state)
            }
        }
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(top = 6.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            phases.forEach { phase ->
                Text(
                    text = phase.label,
                    style = MaterialTheme.typography.labelSmall,
                    color = if (phase.state == musePhaseState.Current) JarvisSignal
                            else JarvisSignalMute,
                )
            }
        }
    }
}

@Composable
private fun PhaseNode(state: musePhaseState, modifier: Modifier = Modifier) {
    Canvas(
        modifier = modifier
            .width(20.dp)
            .height(20.dp),
    ) {
        val r = minOf(size.width, size.height) / 2f
        val centre = Offset(size.width / 2f, size.height / 2f)
        val node = r * 0.62f
        when (state) {
            musePhaseState.Done -> drawCircle(
                color = JarvisCyan,
                radius = node,
                center = centre,
                style = Stroke(width = r * 0.22f),
            )
            musePhaseState.Current -> {
                // Tight cool bloom + the white core.
                drawCircle(color = JarvisGold.copy(alpha = 0.25f), radius = node * 1.7f, center = centre)
                drawCircle(color = JarvisGold, radius = node, center = centre)
            }
            musePhaseState.Failed -> drawCircle(color = JarvisCrimson, radius = node, center = centre)
            musePhaseState.Pending -> drawCircle(
                color = JarvisSignalMute,
                radius = node,
                center = centre,
                style = Stroke(width = r * 0.18f),
            )
        }
    }
}

@Composable
private fun PhaseConnector(lit: Boolean, modifier: Modifier = Modifier) {
    Canvas(
        modifier = modifier
            .height(20.dp)
            .padding(horizontal = 2.dp),
    ) {
        val y = size.height / 2f
        drawLine(
            color = if (lit) JarvisCyan else JarvisInkEdge,
            start = Offset(0f, y),
            end = Offset(size.width, y),
            strokeWidth = 2.dp.toPx(),
            cap = StrokeCap.Round,
        )
    }
}
