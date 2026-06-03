package com.aci.hermes.approval.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.aci.hermes.R
import com.aci.hermes.approval.model.ApprovalRiskTier
import com.aci.hermes.approval.model.ApprovalStatus

// Severity palette for the badges. These are deliberately the GitHub-style
// fixed severity colors (high white-on-color contrast in both themes) rather
// than the Jarvis accent tokens — re-pointing them would lower the badge
// contrast. The labels are localized via string resources.

@Composable
fun TierBadge(tier: ApprovalRiskTier, modifier: Modifier = Modifier) {
    val label = stringResource(tier.labelRes())
    val color = when (tier) {
        ApprovalRiskTier.SAFE -> Color(0xFF1F883D)
        ApprovalRiskTier.LOW -> Color(0xFF2DA44E)
        ApprovalRiskTier.RISKY -> Color(0xFFBF8700)
        ApprovalRiskTier.SERIOUS -> Color(0xFFD1242F)
        ApprovalRiskTier.CRITICAL -> Color(0xFF82071E)
        ApprovalRiskTier.FORBIDDEN -> Color(0xFF4D0810)
    }
    Row(
        modifier = modifier
            .background(color, RoundedCornerShape(50))
            .padding(horizontal = 8.dp, vertical = 2.dp),
        horizontalArrangement = Arrangement.Center
    ) {
        Text(label, color = Color.White, style = MaterialTheme.typography.labelSmall)
    }
}

@Composable
fun StatusBadge(status: ApprovalStatus, modifier: Modifier = Modifier) {
    val label = stringResource(status.labelRes())
    val color = when (status) {
        ApprovalStatus.PENDING -> Color(0xFF656D76)
        ApprovalStatus.APPROVED -> Color(0xFF1F883D)
        ApprovalStatus.REJECTED -> Color(0xFFD1242F)
        ApprovalStatus.EXPIRED -> Color(0xFF7D8590)
        ApprovalStatus.EMERGENCY_STOPPED -> Color(0xFF82071E)
    }
    Row(
        modifier = modifier
            .background(color, RoundedCornerShape(50))
            .padding(horizontal = 8.dp, vertical = 2.dp)
    ) {
        Text(label, color = Color.White, style = MaterialTheme.typography.labelSmall)
    }
}

private fun ApprovalRiskTier.labelRes(): Int = when (this) {
    ApprovalRiskTier.SAFE -> R.string.approval_tier_safe
    ApprovalRiskTier.LOW -> R.string.approval_tier_low
    ApprovalRiskTier.RISKY -> R.string.approval_tier_risky
    ApprovalRiskTier.SERIOUS -> R.string.approval_tier_serious
    ApprovalRiskTier.CRITICAL -> R.string.approval_tier_critical
    ApprovalRiskTier.FORBIDDEN -> R.string.approval_tier_forbidden
}

private fun ApprovalStatus.labelRes(): Int = when (this) {
    ApprovalStatus.PENDING -> R.string.approval_status_pending
    ApprovalStatus.APPROVED -> R.string.approval_status_approved
    ApprovalStatus.REJECTED -> R.string.approval_status_rejected
    ApprovalStatus.EXPIRED -> R.string.approval_status_expired
    ApprovalStatus.EMERGENCY_STOPPED -> R.string.approval_status_emergency_stopped
}
