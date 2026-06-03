package com.aci.hermes.ui.components

import androidx.compose.foundation.BorderStroke
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
import com.aci.hermes.approval.model.ApprovalRiskTier
import com.aci.hermes.data.model.TaskStatus
import com.aci.hermes.ui.theme.JarvisAmber
import com.aci.hermes.ui.theme.JarvisCrimson
import com.aci.hermes.ui.theme.JarvisCyan
import com.aci.hermes.ui.theme.JarvisGold
import com.aci.hermes.ui.theme.JarvisJade
import com.aci.hermes.ui.theme.JarvisTokens

/**
 * Semantic tone for a [StatusChip]. Pure (no Compose / Android types) so the
 * status→tone and risk→tone mappings below are unit-tested directly. The
 * composable layer resolves a tone to a concrete color via [color].
 */
enum class ChipTone { NEUTRAL, INFO, ACTIVE, WARN, DANGER, SUCCESS }

/** Task lifecycle → tone. High-risk-adjacent states (needs revision) read danger. */
fun TaskStatus.chipTone(): ChipTone = when (this) {
    TaskStatus.DRAFT -> ChipTone.NEUTRAL
    TaskStatus.READY_FOR_HANDOFF -> ChipTone.INFO
    TaskStatus.HANDED_TO_CODEX, TaskStatus.HANDED_TO_CLAUDE -> ChipTone.ACTIVE
    TaskStatus.IN_REVIEW -> ChipTone.INFO
    TaskStatus.NEEDS_REVISION -> ChipTone.DANGER
    TaskStatus.COMPLETE -> ChipTone.SUCCESS
}

/** Risk tier → tone, so a high-risk task reads at a glance (crimson). */
fun ApprovalRiskTier.chipTone(): ChipTone = when (this) {
    ApprovalRiskTier.SAFE, ApprovalRiskTier.LOW -> ChipTone.SUCCESS
    ApprovalRiskTier.RISKY -> ChipTone.WARN
    ApprovalRiskTier.SERIOUS, ApprovalRiskTier.CRITICAL, ApprovalRiskTier.FORBIDDEN -> ChipTone.DANGER
}

@Composable
fun ChipTone.color(): Color = when (this) {
    ChipTone.NEUTRAL -> MaterialTheme.colorScheme.onSurfaceVariant
    ChipTone.INFO -> JarvisCyan
    ChipTone.ACTIVE -> JarvisGold
    ChipTone.WARN -> JarvisAmber
    ChipTone.DANGER -> JarvisCrimson
    ChipTone.SUCCESS -> JarvisJade
}

/**
 * Compact, theme-safe status pill: a tone-colored dot + label inside a
 * surface-variant pill with a hairline tone border. Display-only — the
 * enclosing card owns the tap, so the chip is not a competing touch target.
 */
@Composable
fun StatusChip(
    label: String,
    tone: ChipTone,
    modifier: Modifier = Modifier,
) {
    val color = tone.color()
    Surface(
        shape = JarvisTokens.ShapePill,
        color = MaterialTheme.colorScheme.surfaceVariant,
        border = BorderStroke(JarvisTokens.BorderHairline, color.copy(alpha = 0.5f)),
        modifier = modifier.height(JarvisTokens.PillHeight),
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm),
            modifier = Modifier.padding(horizontal = JarvisTokens.SpaceMd),
        ) {
            Surface(shape = CircleShape, color = color, modifier = Modifier.size(8.dp), content = {})
            Text(
                text = label,
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}
