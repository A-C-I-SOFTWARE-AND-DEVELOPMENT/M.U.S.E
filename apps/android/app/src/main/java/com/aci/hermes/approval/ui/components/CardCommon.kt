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
import androidx.compose.ui.unit.dp
import com.aci.hermes.approval.model.ApprovalRiskTier
import com.aci.hermes.approval.model.ApprovalStatus

@Composable
fun TierBadge(tier: ApprovalRiskTier, modifier: Modifier = Modifier) {
    val (label, color) = when (tier) {
        ApprovalRiskTier.SAFE -> "SAFE" to Color(0xFF1F883D)
        ApprovalRiskTier.LOW -> "LOW" to Color(0xFF2DA44E)
        ApprovalRiskTier.RISKY -> "RISKY" to Color(0xFFBF8700)
        ApprovalRiskTier.SERIOUS -> "SERIOUS" to Color(0xFFD1242F)
        ApprovalRiskTier.CRITICAL -> "CRITICAL" to Color(0xFF82071E)
        ApprovalRiskTier.FORBIDDEN -> "FORBIDDEN" to Color(0xFF4D0810)
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
    val (label, color) = when (status) {
        ApprovalStatus.PENDING -> "Pending" to Color(0xFF656D76)
        ApprovalStatus.APPROVED -> "Approved" to Color(0xFF1F883D)
        ApprovalStatus.REJECTED -> "Rejected" to Color(0xFFD1242F)
        ApprovalStatus.EXPIRED -> "Expired" to Color(0xFF7D8590)
        ApprovalStatus.EMERGENCY_STOPPED -> "Emergency stopped" to Color(0xFF82071E)
    }
    Row(
        modifier = modifier
            .background(color, RoundedCornerShape(50))
            .padding(horizontal = 8.dp, vertical = 2.dp)
    ) {
        Text(label, color = Color.White, style = MaterialTheme.typography.labelSmall)
    }
}
