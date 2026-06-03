package com.aci.hermes.ui.screens.ledger

import androidx.compose.material3.ColorScheme
import androidx.compose.ui.graphics.Color
import com.aci.hermes.data.model.ledger.LedgerCategory
import java.time.Instant
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

private val tsFormatter: DateTimeFormatter =
    DateTimeFormatter.ofPattern("MMM d, HH:mm", Locale.getDefault())

/** Render an ISO-8601 ledger timestamp as a short local string (raw on failure). */
fun formatLedgerTimestamp(iso: String): String {
    if (iso.isBlank()) return "—"
    return runCatching {
        OffsetDateTime.parse(iso).atZoneSameInstant(ZoneId.systemDefault()).format(tsFormatter)
    }.recoverCatching {
        Instant.parse(iso).atZone(ZoneId.systemDefault()).format(tsFormatter)
    }.getOrDefault(iso)
}

fun LedgerCategory.displayLabel(): String = when (this) {
    LedgerCategory.MODEL_CALL -> "Model call"
    LedgerCategory.TOOL_CALL -> "Tool call"
    LedgerCategory.COMMAND -> "Command"
    LedgerCategory.FILE_EDIT -> "File edit"
    LedgerCategory.WORKER_RUN -> "Worker run"
    LedgerCategory.APPROVAL -> "Approval"
    LedgerCategory.MEMORY_WRITE -> "Memory write"
    LedgerCategory.EVIDENCE_PROMOTION -> "Evidence"
    LedgerCategory.DEPLOY_PUBLISH -> "Deploy / publish"
    LedgerCategory.NAVIGATION -> "Navigation"
    LedgerCategory.VALIDATION -> "Validation"
    LedgerCategory.LIFECYCLE -> "Lifecycle"
}

fun LedgerCategory.colorOn(scheme: ColorScheme): Color = when (this) {
    LedgerCategory.DEPLOY_PUBLISH -> scheme.error
    LedgerCategory.APPROVAL, LedgerCategory.VALIDATION -> scheme.secondary
    LedgerCategory.WORKER_RUN, LedgerCategory.COMMAND, LedgerCategory.FILE_EDIT -> scheme.primary
    else -> scheme.onSurfaceVariant
}

/** The canonical risk-filter vocabulary the timeline filter row offers. */
val RISK_FILTER_OPTIONS: List<String> =
    listOf("LOW", "MODERATE", "SERIOUS", "CRITICAL")
