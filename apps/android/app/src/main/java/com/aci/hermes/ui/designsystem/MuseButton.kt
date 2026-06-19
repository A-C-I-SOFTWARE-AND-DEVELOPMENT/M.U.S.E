package com.aci.hermes.ui.designsystem

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.size
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.unit.dp
import com.aci.hermes.ui.theme.JarvisGold
import com.aci.hermes.ui.theme.JarvisInkAbyss
import com.aci.hermes.ui.theme.JarvisInkDeep
import com.aci.hermes.ui.theme.JarvisInkEdge
import com.aci.hermes.ui.theme.JarvisJade
import com.aci.hermes.ui.theme.JarvisSignal
import com.aci.hermes.ui.theme.JarvisSignalGhost
import com.aci.hermes.ui.theme.JarvisCrimson
import com.aci.hermes.ui.theme.JarvisTokens

/**
 * The kinds of action a muse button can express. Valence is carried by the
 * button, not the label — so the surface reads the same everywhere.
 */
enum class museButtonVariant {
    /** The single hero action: white core fill, dark text. Use one per view. */
    Primary,

    /** Quiet / cancel-adjacent: void-3 fill with a hairline edge border. */
    Secondary,

    /** Destructive / emergency stop: danger surface. */
    Danger,

    /** Owner-gate approval: the "Yes, with authorization" affordance. */
    Approve,
}

/**
 * The muse button.
 *
 * One component, four [variants][museButtonVariant]. The primary is the white
 * incandescent core itself rendered as a CTA (white fill, void text) — there
 * should only ever be one per view, mirroring "nothing outshines the core."
 * Secondary recedes to void-3 with an edge hairline; danger and approve carry
 * the UI status colors (which never appear in brand *art*, but are correct on
 * interactive controls).
 *
 * @param onClick invoked on tap when [enabled].
 * @param text the button label.
 * @param variant which valence to render. Defaults to [museButtonVariant.Primary].
 * @param enabled when false, the button dims and ignores taps.
 * @param leadingIcon optional icon drawn before the label.
 */
@Composable
fun museButton(
    onClick: () -> Unit,
    text: String,
    modifier: Modifier = Modifier,
    variant: museButtonVariant = museButtonVariant.Primary,
    enabled: Boolean = true,
    leadingIcon: ImageVector? = null,
) {
    val colors = when (variant) {
        museButtonVariant.Primary -> ButtonDefaults.buttonColors(
            containerColor = JarvisGold,
            contentColor = JarvisInkAbyss,
            disabledContainerColor = JarvisInkDeep,
            disabledContentColor = JarvisSignalGhost,
        )
        museButtonVariant.Secondary -> ButtonDefaults.buttonColors(
            containerColor = JarvisInkDeep,
            contentColor = JarvisSignal,
            disabledContainerColor = JarvisInkDeep,
            disabledContentColor = JarvisSignalGhost,
        )
        museButtonVariant.Danger -> ButtonDefaults.buttonColors(
            containerColor = JarvisCrimson,
            contentColor = JarvisInkAbyss,
            disabledContainerColor = JarvisInkDeep,
            disabledContentColor = JarvisSignalGhost,
        )
        museButtonVariant.Approve -> ButtonDefaults.buttonColors(
            containerColor = JarvisJade,
            contentColor = JarvisInkAbyss,
            disabledContainerColor = JarvisInkDeep,
            disabledContentColor = JarvisSignalGhost,
        )
    }

    // Only the secondary (quiet) variant carries a visible frame; the filled
    // variants are defined by their fill, not a border.
    val border: BorderStroke? = when (variant) {
        museButtonVariant.Secondary ->
            BorderStroke(JarvisTokens.BorderHairline, if (enabled) JarvisInkEdge else JarvisInkDeep)
        else -> null
    }

    Button(
        onClick = onClick,
        modifier = modifier,
        enabled = enabled,
        shape = JarvisTokens.ShapeButton,
        colors = colors,
        border = border,
    ) {
        if (leadingIcon != null) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm),
            ) {
                Icon(
                    imageVector = leadingIcon,
                    contentDescription = null,
                    modifier = Modifier.size(18.dp),
                )
                Text(text = text, style = MaterialTheme.typography.labelLarge)
            }
        } else {
            Text(text = text, style = MaterialTheme.typography.labelLarge)
        }
    }
}
