package com.aci.hermes.ui.components

import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import com.aci.hermes.R
import com.aci.hermes.ui.theme.JarvisTokens

/**
 * Audit card — entry point into the immutable Jarvis action log.
 */
@Composable
fun AuditCard(
    onOpen: () -> Unit,
    modifier: Modifier = Modifier,
) {
    CommandCard(
        title = stringResource(R.string.audit_card_title),
        subtitle = stringResource(R.string.audit_card_subtitle),
        tier = CardTier.MEMORY,
        modifier = modifier,
    ) {
        OutlinedButton(
            onClick = onOpen,
            shape = JarvisTokens.ShapeButton,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text(stringResource(R.string.audit_open))
        }
    }
}
