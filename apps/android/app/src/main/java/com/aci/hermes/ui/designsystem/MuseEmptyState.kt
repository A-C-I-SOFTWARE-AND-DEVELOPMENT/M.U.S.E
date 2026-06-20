package com.aci.hermes.ui.designsystem

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.aci.hermes.ui.theme.JarvisSignal
import com.aci.hermes.ui.theme.JarvisSignalDim
import com.aci.hermes.ui.theme.JarvisTokens

/**
 * The muse empty state — the [museGlyph] over a void, a title, a body, and an
 * optional action. The pattern for "nothing here yet" panels (no jobs, no
 * memory, no approvals) so empty screens still feel like the product, not a
 * blank.
 *
 * Centered, with generous negative space (a brand rule). The glyph carries the
 * brand; the title is signal-bright; the body steps down to dim — the value
 * ladder again.
 *
 * @param title the headline (e.g. "No active jobs").
 * @param body the supporting sentence under the title.
 * @param actionLabel optional CTA label; when set together with [onAction],
 *                    a primary [museButton] is shown.
 * @param onAction tap handler for the action button.
 */
@Composable
fun museEmptyState(
    title: String,
    body: String,
    modifier: Modifier = Modifier,
    actionLabel: String? = null,
    onAction: (() -> Unit)? = null,
) {
    Column(
        modifier = modifier
            .fillMaxWidth()
            .padding(JarvisTokens.SpaceXxl),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceLg),
    ) {
        museGlyph(size = 72.dp)
        Text(
            text = title,
            style = MaterialTheme.typography.titleLarge,
            color = JarvisSignal,
            textAlign = TextAlign.Center,
        )
        Text(
            text = body,
            style = MaterialTheme.typography.bodyMedium,
            color = JarvisSignalDim,
            textAlign = TextAlign.Center,
            modifier = Modifier.widthIn(max = 320.dp),
        )
        if (actionLabel != null && onAction != null) {
            museButton(
                onClick = onAction,
                text = actionLabel,
                variant = museButtonVariant.Primary,
                modifier = Modifier.padding(top = JarvisTokens.SpaceSm),
            )
        }
    }
}
