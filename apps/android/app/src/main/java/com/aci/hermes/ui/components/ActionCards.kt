package com.aci.hermes.ui.components

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import com.aci.hermes.R
import com.aci.hermes.ui.theme.JarvisCrimson
import com.aci.hermes.ui.theme.JarvisGold
import com.aci.hermes.ui.theme.JarvisInkAbyss
import com.aci.hermes.ui.theme.JarvisSignal
import com.aci.hermes.ui.theme.JarvisTokens

/**
 * Approval card — Jarvis wants permission to proceed. Gold-bordered,
 * positive default action, optional "see details" affordance.
 */
@Composable
fun ApprovalCard(
    onApprove: () -> Unit,
    onDeny: () -> Unit,
    modifier: Modifier = Modifier,
    title: String = stringResource(R.string.approval_title),
    body: String = stringResource(R.string.approval_body),
    onDetails: (() -> Unit)? = null,
) {
    CommandCard(
        title = title,
        subtitle = body,
        tier = CardTier.APPROVAL,
        modifier = modifier,
    ) {
        Row(
            horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm),
            modifier = Modifier.fillMaxWidth(),
        ) {
            Button(
                onClick = onApprove,
                shape = JarvisTokens.ShapeButton,
                colors = ButtonDefaults.buttonColors(
                    containerColor = JarvisGold,
                    contentColor = JarvisInkAbyss,
                )
            ) {
                Text(stringResource(R.string.approval_approve))
            }
            OutlinedButton(
                onClick = onDeny,
                shape = JarvisTokens.ShapeButton,
            ) {
                Text(stringResource(R.string.approval_deny))
            }
            if (onDetails != null) {
                TextButton(onClick = onDetails) {
                    Text(stringResource(R.string.approval_details))
                }
            }
        }
    }
}

/**
 * Serious action card — meaningful but reversible. Amber-bordered.
 */
@Composable
fun SeriousActionCard(
    onConfirm: () -> Unit,
    onCancel: () -> Unit,
    modifier: Modifier = Modifier,
    title: String = stringResource(R.string.serious_title),
    body: String = stringResource(R.string.serious_body),
    onReview: (() -> Unit)? = null,
) {
    CommandCard(
        title = title,
        subtitle = body,
        tier = CardTier.SERIOUS,
        modifier = modifier,
    ) {
        Row(
            horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm),
            modifier = Modifier.fillMaxWidth(),
        ) {
            Button(
                onClick = onConfirm,
                shape = JarvisTokens.ShapeButton,
                colors = ButtonDefaults.buttonColors(
                    containerColor = JarvisGold,
                    contentColor = JarvisInkAbyss,
                ),
            ) {
                Text(stringResource(R.string.serious_confirm))
            }
            if (onReview != null) {
                OutlinedButton(onClick = onReview, shape = JarvisTokens.ShapeButton) {
                    Text(stringResource(R.string.serious_review))
                }
            }
            TextButton(onClick = onCancel) {
                Text(stringResource(R.string.action_cancel))
            }
        }
    }
}

/**
 * Critical action card — destructive, irreversible. Crimson-bordered;
 * confirm button is also crimson so it is impossible to miss.
 */
@Composable
fun CriticalActionCard(
    onConfirm: () -> Unit,
    onCancel: () -> Unit,
    modifier: Modifier = Modifier,
    title: String = stringResource(R.string.critical_title),
    body: String = stringResource(R.string.critical_body),
) {
    CommandCard(
        title = title,
        subtitle = body,
        tier = CardTier.CRITICAL,
        modifier = modifier,
    ) {
        Row(
            horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm),
            modifier = Modifier.fillMaxWidth(),
        ) {
            Button(
                onClick = onConfirm,
                shape = JarvisTokens.ShapeButton,
                colors = ButtonDefaults.buttonColors(
                    containerColor = JarvisCrimson,
                    contentColor = JarvisSignal,
                ),
            ) {
                Text(stringResource(R.string.critical_confirm))
            }
            OutlinedButton(onClick = onCancel, shape = JarvisTokens.ShapeButton) {
                Text(stringResource(R.string.critical_cancel))
            }
        }
    }
}
