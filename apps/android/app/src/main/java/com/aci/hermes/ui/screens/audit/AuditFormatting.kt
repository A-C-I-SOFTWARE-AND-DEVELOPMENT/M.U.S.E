package com.aci.hermes.ui.screens.audit

import androidx.compose.ui.graphics.Color
import androidx.compose.material3.ColorScheme
import com.aci.hermes.data.model.audit.ActionResult
import com.aci.hermes.data.model.audit.ApprovalState
import com.aci.hermes.data.model.audit.RiskTier
import com.aci.hermes.data.model.audit.RouteDestination
import com.aci.hermes.data.model.audit.VerificationStatus
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

private val timestampFormatter = SimpleDateFormat("MMM d, HH:mm", Locale.getDefault())

fun formatTimestamp(epochMillis: Long): String =
    timestampFormatter.format(Date(epochMillis))

fun RiskTier.displayLabel(): String = when (this) {
    RiskTier.TRIVIAL -> "Trivial"
    RiskTier.LOW -> "Low"
    RiskTier.MODERATE -> "Moderate"
    RiskTier.SERIOUS -> "Serious"
    RiskTier.CRITICAL -> "Critical"
}

fun ApprovalState.displayLabel(): String = when (this) {
    ApprovalState.UNNECESSARY -> "No approval needed"
    ApprovalState.PENDING -> "Pending approval"
    ApprovalState.APPROVED -> "Approved"
    ApprovalState.REJECTED -> "Rejected"
    ApprovalState.AUTO_APPROVED -> "Auto-approved"
    ApprovalState.EXPIRED -> "Expired"
}

fun ActionResult.displayLabel(): String = when (this) {
    ActionResult.SUCCESS -> "Success"
    ActionResult.PARTIAL -> "Partial"
    ActionResult.FAILED -> "Failed"
    ActionResult.ROLLED_BACK -> "Rolled back"
    ActionResult.BLOCKED -> "Blocked"
}

fun RouteDestination.displayLabel(): String = when (this) {
    RouteDestination.LOCAL_WORKER -> "Local worker"
    RouteDestination.CODEX -> "Codex"
    RouteDestination.CLAUDE -> "Claude"
    RouteDestination.HERMES_GATEWAY -> "muse gateway"
    RouteDestination.HUMAN_ONLY -> "Human only"
}

fun VerificationStatus.displayLabel(): String = when (this) {
    VerificationStatus.PASSED -> "Passed"
    VerificationStatus.FAILED -> "Failed"
    VerificationStatus.SKIPPED -> "Skipped"
    VerificationStatus.FLAKY -> "Flaky"
}

fun ActionResult.isFailureLike(): Boolean = when (this) {
    ActionResult.FAILED, ActionResult.ROLLED_BACK, ActionResult.BLOCKED -> true
    else -> false
}

fun RiskTier.colorOn(scheme: ColorScheme): Color = when (this) {
    RiskTier.TRIVIAL, RiskTier.LOW -> scheme.primary
    RiskTier.MODERATE -> scheme.secondary
    RiskTier.SERIOUS, RiskTier.CRITICAL -> scheme.error
}

fun ActionResult.colorOn(scheme: ColorScheme): Color = when (this) {
    ActionResult.SUCCESS -> scheme.primary
    ActionResult.PARTIAL -> scheme.secondary
    ActionResult.FAILED, ActionResult.ROLLED_BACK, ActionResult.BLOCKED -> scheme.error
}

fun VerificationStatus.colorOn(scheme: ColorScheme): Color = when (this) {
    VerificationStatus.PASSED -> scheme.primary
    VerificationStatus.FAILED -> scheme.error
    VerificationStatus.SKIPPED -> scheme.onSurfaceVariant
    VerificationStatus.FLAKY -> scheme.secondary
}

fun ApprovalState.colorOn(scheme: ColorScheme): Color = when (this) {
    ApprovalState.APPROVED, ApprovalState.AUTO_APPROVED -> scheme.primary
    ApprovalState.PENDING -> scheme.secondary
    ApprovalState.REJECTED, ApprovalState.EXPIRED -> scheme.error
    ApprovalState.UNNECESSARY -> scheme.onSurfaceVariant
}

fun confidenceLabel(confidence: Float): String {
    if (confidence <= 0f) return "—"
    val pct = (confidence * 100).toInt()
    return "$pct% confidence"
}
