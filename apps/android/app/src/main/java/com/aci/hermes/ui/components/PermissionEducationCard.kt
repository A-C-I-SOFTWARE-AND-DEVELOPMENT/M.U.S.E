package com.aci.hermes.ui.components

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import com.aci.hermes.R
import com.aci.hermes.ui.theme.JarvisGold
import com.aci.hermes.ui.theme.JarvisInkAbyss
import com.aci.hermes.ui.theme.JarvisTokens

/**
 * Permission education card — shown before the system permission prompt.
 *
 * MUSE never asks for a sensitive permission without explaining
 * why. Use the well-known [PermissionKind] enum to pick canned copy;
 * pass an [overrideBody] only if your screen needs a bespoke wording.
 */
enum class PermissionKind { Microphone, Notifications }

@Composable
fun PermissionEducationCard(
    kind: PermissionKind,
    onContinue: () -> Unit,
    onSkip: () -> Unit,
    modifier: Modifier = Modifier,
    overrideBody: String? = null,
) {
    val bodyRes = when (kind) {
        PermissionKind.Microphone    -> R.string.permission_education_microphone_body
        PermissionKind.Notifications -> R.string.permission_education_notifications_body
    }
    val body = overrideBody ?: stringResource(bodyRes)

    CommandCard(
        title = stringResource(R.string.permission_education_title),
        subtitle = body,
        tier = CardTier.ACTIVE,
        modifier = modifier,
    ) {
        Row(
            horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm),
            modifier = Modifier.fillMaxWidth(),
        ) {
            Button(
                onClick = onContinue,
                shape = JarvisTokens.ShapeButton,
                colors = ButtonDefaults.buttonColors(
                    containerColor = JarvisGold,
                    contentColor = JarvisInkAbyss,
                ),
            ) {
                Text(stringResource(R.string.permission_education_continue))
            }
            TextButton(onClick = onSkip) {
                Text(stringResource(R.string.permission_education_not_now))
            }
        }
    }
}
