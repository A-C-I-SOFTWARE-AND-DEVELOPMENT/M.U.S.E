package com.aci.hermes.ui.components

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import com.aci.hermes.R
import com.aci.hermes.ui.theme.JarvisTokens

/**
 * Memory card — Jarvis remembered (or corrected) something.
 *
 * Use [corrected] = true when this is a "memory corrected" follow-up.
 */
@Composable
fun MemoryCard(
    fact: String,
    modifier: Modifier = Modifier,
    corrected: Boolean = false,
    onReview: (() -> Unit)? = null,
    onForget: (() -> Unit)? = null,
) {
    val titleRes = if (corrected) R.string.memory_corrected_title else R.string.memory_card_title
    val bodyRes  = if (corrected) R.string.memory_corrected_body  else R.string.memory_card_body

    CommandCard(
        title = stringResource(titleRes),
        subtitle = stringResource(bodyRes, fact),
        tier = CardTier.MEMORY,
        modifier = modifier,
    ) {
        Row(
            horizontalArrangement = Arrangement.spacedBy(JarvisTokens.SpaceSm),
            modifier = Modifier.fillMaxWidth(),
        ) {
            if (onReview != null) {
                OutlinedButton(onClick = onReview, shape = JarvisTokens.ShapeButton) {
                    Text(stringResource(R.string.memory_view))
                }
            }
            if (onForget != null) {
                TextButton(onClick = onForget) {
                    Text(stringResource(R.string.memory_forget))
                }
            }
        }
    }
}
