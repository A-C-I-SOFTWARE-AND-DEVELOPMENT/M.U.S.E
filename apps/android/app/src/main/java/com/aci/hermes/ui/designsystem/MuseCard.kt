package com.aci.hermes.ui.designsystem

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.aci.hermes.ui.theme.JarvisInkDeep
import com.aci.hermes.ui.theme.JarvisInkEdge

/**
 * The MUSE surface card.
 *
 * Void-3 fill ([JarvisInkDeep]) with an [edge][JarvisInkEdge] hairline frame
 * and a 12dp radius — the "command-center framed panel." Elevation is tonal /
 * value, never a drop shadow (a brand rule: use value, not effects, for depth),
 * so both shadow and tonal elevation are zeroed and the frame does the work.
 *
 * @param content the card body, laid out in a [ColumnScope] so callers can
 *                stack rows with their own padding.
 */
@Composable
fun MuseCard(
    modifier: Modifier = Modifier,
    content: @Composable ColumnScope.() -> Unit,
) {
    Card(
        modifier = modifier,
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = JarvisInkDeep),
        // No drop shadow — depth comes from the void/edge value step.
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
        border = BorderStroke(1.dp, JarvisInkEdge),
        content = content,
    )
}
