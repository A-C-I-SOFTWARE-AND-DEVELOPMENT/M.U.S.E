package com.aci.hermes.ui.components

import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
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
import com.aci.hermes.ui.theme.JarvisInkDeep
import com.aci.hermes.ui.theme.JarvisInkEdge
import com.aci.hermes.ui.theme.JarvisSignal
import com.aci.hermes.ui.theme.JarvisSignalDim
import com.aci.hermes.ui.theme.JarvisTokens

/**
 * Tier ladder for command-center cards.
 *
 * - INFO       (calm): default surface, no accent border
 * - ACTIVE     (gold): standard "Muse is on this"
 * - LISTENING  (cyan): live capture, scanning, ambient
 * - APPROVAL   (gold + glow): user must approve
 * - SERIOUS    (amber): meaningful change, confirm intent
 * - CRITICAL   (crimson): destructive / irreversible, hard stop
 * - SUCCESS    (jade): task complete
 * - MEMORY     (violet): memory / audit
 *
 * Each tier maps to a deterministic accent colour; cards use this so the
 * visual language stays consistent across screens.
 */
enum class CardTier(internal val accent: Color, internal val accentDim: Color) {
    INFO(Color.Transparent, JarvisInkEdge),
    ACTIVE(com.aci.hermes.ui.theme.JarvisGold,    com.aci.hermes.ui.theme.JarvisGoldDeep),
    LISTENING(com.aci.hermes.ui.theme.JarvisCyan, com.aci.hermes.ui.theme.JarvisCyanDeep),
    APPROVAL(com.aci.hermes.ui.theme.JarvisGold,  com.aci.hermes.ui.theme.JarvisGoldDeep),
    SERIOUS(com.aci.hermes.ui.theme.JarvisAmber,  com.aci.hermes.ui.theme.JarvisAmber),
    CRITICAL(com.aci.hermes.ui.theme.JarvisCrimson, com.aci.hermes.ui.theme.JarvisCrimsonDeep),
    SUCCESS(com.aci.hermes.ui.theme.JarvisJade,   com.aci.hermes.ui.theme.JarvisJadeDeep),
    MEMORY(com.aci.hermes.ui.theme.JarvisViolet,  com.aci.hermes.ui.theme.JarvisViolet)
}

/**
 * Premium "command-center" card.
 *
 * Deep-navy surface, hairline tier-coloured border, optional title +
 * subtitle row with a small leading dot. The card body is provided by
 * the caller — keeps it reusable across approval, task, memory, etc.
 */
@Composable
fun CommandCard(
    title: String,
    modifier: Modifier = Modifier,
    subtitle: String? = null,
    tier: CardTier = CardTier.INFO,
    leadingDot: Boolean = tier != CardTier.INFO,
    content: @Composable () -> Unit,
) {
    Surface(
        shape = JarvisTokens.ShapeCardLarge,
        color = JarvisInkDeep,
        modifier = modifier
            .fillMaxWidth()
            .border(
                width = JarvisTokens.BorderHairline,
                color = if (tier == CardTier.INFO) JarvisInkEdge else tier.accent.copy(alpha = 0.55f),
                shape = JarvisTokens.ShapeCardLarge,
            )
    ) {
        Column(
            verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceMd),
            modifier = Modifier.padding(JarvisTokens.SpaceLg)
        ) {
            Row(
                verticalAlignment = Alignment.Top,
                horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceMd),
            ) {
                if (leadingDot) {
                    Surface(
                        color = tier.accent,
                        shape = CircleShape,
                        modifier = Modifier
                            .padding(top = 6.dp)
                            .size(8.dp),
                        content = {}
                    )
                }
                Column(
                    modifier = Modifier.fillMaxWidth(),
                    verticalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceXxs),
                ) {
                    Text(
                        text = title,
                        style = MaterialTheme.typography.titleMedium,
                        color = if (tier == CardTier.INFO) JarvisSignal else tier.accent,
                    )
                    if (!subtitle.isNullOrBlank()) {
                        Text(
                            text = subtitle,
                            style = MaterialTheme.typography.bodyMedium,
                            color = JarvisSignalDim,
                        )
                    }
                }
            }
            content()
        }
    }
}
