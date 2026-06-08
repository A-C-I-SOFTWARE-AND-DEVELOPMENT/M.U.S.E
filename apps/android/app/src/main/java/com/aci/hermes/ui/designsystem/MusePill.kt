package com.aci.hermes.ui.designsystem

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp
import com.aci.hermes.ui.theme.JarvisInkEdge
import com.aci.hermes.ui.theme.JarvisInkRaised
import com.aci.hermes.ui.theme.JarvisSignal
import com.aci.hermes.ui.theme.JarvisSignalDim
import com.aci.hermes.ui.theme.JarvisTokens

/**
 * A status pill: a [MuseStatusDot] + a short label inside a rounded raised
 * capsule. The everyday "Connected / Listening / Offline" tell for headers and
 * job rows. The label color follows the status (muted when off).
 *
 * @param status which connection state to show.
 * @param label the text beside the dot (e.g. "Listening", "Offline").
 * @param animate forwarded to the dot's connecting pulse.
 */
@Composable
fun MuseStatusPill(
    status: MuseStatus,
    label: String,
    modifier: Modifier = Modifier,
    animate: Boolean = true,
) {
    val textColor = if (status == MuseStatus.Off) JarvisSignalDim else JarvisSignal
    Row(
        modifier = modifier
            .clip(JarvisTokens.ShapePill)
            .background(JarvisInkRaised)
            .border(JarvisTokens.BorderHairline, JarvisInkEdge, JarvisTokens.ShapePill)
            .padding(horizontal = JarvisTokens.SpaceMd, vertical = JarvisTokens.SpaceXs),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm),
    ) {
        MuseStatusDot(status = status, size = 8.dp, animate = animate)
        Text(
            text = label,
            style = MaterialTheme.typography.labelMedium,
            color = textColor,
        )
    }
}

/**
 * A neutral chip — a small, optionally-selectable label capsule for tags,
 * filters, and metadata. Selection lifts the fill to the white core (with
 * void text) so the "on" chip reads as the single bright thing in its row.
 *
 * @param label the chip text.
 * @param selected when true, renders the selected (core-fill) treatment.
 * @param onClick optional tap handler; when null the chip is display-only.
 */
@Composable
fun MuseChip(
    label: String,
    modifier: Modifier = Modifier,
    selected: Boolean = false,
    onClick: (() -> Unit)? = null,
) {
    val container = if (selected) com.aci.hermes.ui.theme.JarvisGold else JarvisInkRaised
    val content = if (selected) com.aci.hermes.ui.theme.JarvisInkAbyss else JarvisSignalDim
    val border: BorderStroke? =
        if (selected) null else BorderStroke(JarvisTokens.BorderHairline, JarvisInkEdge)

    val base = modifier
        .clip(JarvisTokens.ShapePill)
        .background(container)
        .let { m -> if (border != null) m.border(border, JarvisTokens.ShapePill) else m }
        .let { m -> if (onClick != null) m.clickable(onClick = onClick) else m }
        .padding(horizontal = JarvisTokens.SpaceMd, vertical = 6.dp)

    Row(modifier = base, verticalAlignment = Alignment.CenterVertically) {
        Text(
            text = label,
            style = MaterialTheme.typography.labelMedium,
            color = content,
        )
    }
}
