package com.aci.hermes.ui.designsystem

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextOverflow
import com.aci.hermes.ui.theme.JarvisSignal
import com.aci.hermes.ui.theme.JarvisSignalMute
import com.aci.hermes.ui.theme.JarvisTokens

/**
 * A section header — a title, an optional supporting subtitle, and an optional
 * trailing slot (a "See all" action, a count, a [museStatusPill], …). Used to
 * label groups of cards on a screen.
 *
 * The title is signal-bright; the subtitle steps down to muted, holding the
 * value ladder (the eye lands on the title first).
 *
 * @param title the section label.
 * @param subtitle optional one-line supporting text under the title.
 * @param trailing optional composable pinned to the end of the header row.
 */
@Composable
fun museSectionHeader(
    title: String,
    modifier: Modifier = Modifier,
    subtitle: String? = null,
    trailing: (@Composable () -> Unit)? = null,
) {
    Row(
        modifier = modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Column(
            modifier = Modifier.weight(1f),
            verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceXxs),
        ) {
            Text(
                text = title,
                style = MaterialTheme.typography.titleMedium,
                color = JarvisSignal,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            if (subtitle != null) {
                Text(
                    text = subtitle,
                    style = MaterialTheme.typography.bodySmall,
                    color = JarvisSignalMute,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }
        if (trailing != null) {
            trailing()
        }
    }
}
