package com.aci.hermes.data.learning

import com.aci.hermes.data.cockpit.CockpitLearningCard

/**
 * A learning-dataset candidate awaiting owner review, as shown in the
 * cockpit Learning Queue.
 *
 * Provenance-first: every candidate carries where it came from and which
 * quality gates it has cleared, so the owner approves source-backed traces
 * rather than opaque blobs. The raw trace payload is intentionally *not*
 * carried to the device — the gateway already scrubbed secrets at write
 * time and the list surface shows only the audit-card projection.
 */
data class LearningCandidate(
    val id: String,
    val title: String,
    val traceType: String,
    val status: LearningStatus,
    val labels: List<String>,
    val isNegative: Boolean,
    val quality: LearningQuality,
    val sourceKind: String,
    val sourceUri: String,
    val citations: List<String>,
    val createdAt: String?,
)

enum class LearningStatus { PENDING, APPROVED, REJECTED, EXPORTED, UNKNOWN }

data class LearningQuality(
    val testsPassed: Boolean,
    val citationsVerified: Boolean,
    val ownerApproved: Boolean,
    val reviewerPassed: Boolean,
    val rollbackAvailable: Boolean,
) {
    /** Human-readable gate chips that are satisfied, for compact display. */
    val passedLabels: List<String>
        get() = buildList {
            if (testsPassed) add("tests")
            if (citationsVerified) add("citations")
            if (reviewerPassed) add("review")
            if (rollbackAvailable) add("rollback")
            if (ownerApproved) add("owner")
        }
}

private fun parseStatus(raw: String): LearningStatus = when (raw.lowercase()) {
    "pending" -> LearningStatus.PENDING
    "approved" -> LearningStatus.APPROVED
    "rejected" -> LearningStatus.REJECTED
    "exported" -> LearningStatus.EXPORTED
    else -> LearningStatus.UNKNOWN
}

fun CockpitLearningCard.toCandidate(): LearningCandidate = LearningCandidate(
    id = id,
    title = title.ifBlank { traceType.replace('_', ' ') },
    traceType = traceType,
    status = parseStatus(status),
    labels = labels,
    isNegative = isNegative,
    quality = LearningQuality(
        testsPassed = quality.testsPassed,
        citationsVerified = quality.citationsVerified,
        ownerApproved = quality.ownerApproved,
        reviewerPassed = quality.reviewerPassed,
        rollbackAvailable = quality.rollbackAvailable,
    ),
    sourceKind = provenance.sourceKind,
    sourceUri = provenance.sourceUri,
    citations = provenance.citations,
    createdAt = createdAt,
)
