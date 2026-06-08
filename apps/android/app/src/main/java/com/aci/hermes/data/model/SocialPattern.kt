package com.aci.hermes.data.model

import kotlinx.serialization.Serializable
import java.util.UUID

/**
 * A MUSE Social Speech Pattern.
 *
 * A SocialPattern is an ABSTRACT communication pattern — it captures
 * *how* a class of people typically writes (e.g. "engineers reply
 * short on mobile") without storing who said what. The model is
 * deliberately narrow:
 *
 *  - No usernames, real names, handles, avatars, or profile data.
 *  - No raw comments. The [summary] is a paraphrased generalization.
 *  - No identity attribution. [provenance] points only at public
 *    aggregate sources (style guides, public dataset names, public
 *    blog posts), never at a specific person.
 *
 * The companion redactor [PrivacyRedactor] enforces these invariants
 * at write time, and the UI re-runs the same redactor at render time
 * to prevent leaks from older stored data.
 */
@Serializable
data class SocialPattern(
    val id: String = UUID.randomUUID().toString(),
    val title: String,
    val kind: SocialPatternKind,
    val summary: String,
    val safeUsage: String,
    val unsafeUsage: String,
    val provenance: List<PatternProvenance> = emptyList(),
    val privacyRisk: PrivacyRisk = PrivacyRisk.LOW,
    val identityFlags: List<String> = emptyList(),
    val correctedFrom: String? = null,
    val createdAt: Long = System.currentTimeMillis(),
    val updatedAt: Long = System.currentTimeMillis(),
)

/**
 * Allowed pattern kinds. These are the only categories MUSE
 * may learn — they are abstract speech patterns, never identity.
 */
@Serializable
enum class SocialPatternKind(val displayName: String) {
    COMMUNICATION("Communication pattern"),
    MOBILE_REPLY("Mobile reply pattern"),
    DISAGREEMENT("Disagreement pattern"),
    TRUST_BUILDING("Trust-building pattern"),
    SUPPORT("Support pattern"),
    TECHNICAL_TRIAGE("Technical triage pattern"),
}

/**
 * Privacy risk surfaces in the UI as a colored chip and gates
 * dangerous operations. HIGH always blocks display of the summary
 * and forces the user to delete or correct the pattern.
 */
@Serializable
enum class PrivacyRisk(val label: String) {
    LOW("Low"),
    MEDIUM("Medium"),
    HIGH("High — contains identity"),
}

/**
 * Provenance points at a public, citable source. Private profiles,
 * auth-walled URLs, and identity-bearing strings are rejected by
 * [PrivacyRedactor.sanitizeProvenance].
 */
@Serializable
data class PatternProvenance(
    val sourceTitle: String,
    val sourceUrl: String? = null,
    val sourceKind: ProvenanceKind = ProvenanceKind.PUBLIC_DOC,
    val note: String? = null,
)

@Serializable
enum class ProvenanceKind(val displayName: String) {
    PUBLIC_DOC("Public document"),
    STYLE_GUIDE("Public style guide"),
    PUBLIC_DATASET("Public dataset"),
    PUBLIC_BLOG("Public blog post"),
    AGGREGATE_STATS("Aggregate statistic"),
    USER_TAUGHT("Taught by you"),
}

/**
 * The Memory screen groups patterns by category. The Social Speech
 * Pattern category is the only one defined for now; this enum lets
 * the screen extend later without code changes to the model.
 */
@Serializable
enum class MemoryCategory(val displayName: String) {
    SOCIAL_SPEECH_PATTERN("Social Speech Pattern"),
}
