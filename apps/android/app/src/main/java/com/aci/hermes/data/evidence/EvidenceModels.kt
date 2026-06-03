package com.aci.hermes.data.evidence

import kotlinx.serialization.Serializable

/**
 * JARVIS Evidence Engine — Android domain model.
 *
 * An [EvidenceItem] is one source-cited artifact from the backend Research
 * Vault. The Evidence screen renders these with trust + freshness labels,
 * surfaces contradictions, and lets the owner promote an item to durable
 * memory (gated server-side by the memory write policy). The same shape is
 * what the cockpit gateway syncs over; [EvidenceRepository] supplies a mock
 * seed only when unpaired / in tests.
 */
@Serializable
data class EvidenceItem(
    val id: String,
    val title: String,
    val sourceUri: String,
    val sourceType: String,
    val trust: EvidenceTrust,
    val evidenceStrength: String,
    val excerpt: String,
    val summary: String,
    val tags: List<String> = emptyList(),
    val licenseNotes: String = "",
    val retrievedAt: Long? = null,
    val freshnessDue: Long? = null,
    val checksum: String = "",
    val citationAnchors: List<String> = emptyList(),
    val addedAt: Long? = null,
) {
    /** True once the freshness window has elapsed (re-verification is due). */
    fun isStale(now: Long = System.currentTimeMillis()): Boolean =
        freshnessDue != null && freshnessDue < now
}

/**
 * Source-trust ladder, mirroring the backend `SourceTrust` vocabulary.
 * Higher [weight] ranks first. Unknown wire values map to [UNVERIFIED].
 */
@Serializable
enum class EvidenceTrust(val wire: String, val display: String, val weight: Int) {
    OWNER("owner", "Owner", 6),
    PRIMARY("primary", "Primary source", 5),
    OFFICIAL_DOC("official_doc", "Official docs", 4),
    REPUTABLE("reputable", "Reputable", 3),
    COMMUNITY("community", "Community", 2),
    UNVERIFIED("unverified", "Unverified", 1);

    companion object {
        fun fromWire(value: String?): EvidenceTrust =
            entries.firstOrNull { it.wire.equals(value?.trim(), ignoreCase = true) } ?: UNVERIFIED
    }
}

/** A ranked retrieval hit returned by search / the verify endpoint. */
@Serializable
data class EvidenceHit(
    val kind: String,
    val title: String,
    val uri: String,
    val excerpt: String,
    val trust: EvidenceTrust,
    val score: Float,
    val artifactId: String? = null,
    val citationAnchors: List<String> = emptyList(),
)

/** Result of verifying claims against the evidence base. */
@Serializable
data class EvidenceVerification(
    val citations: List<ClaimCitation> = emptyList(),
    val uncertain: List<String> = emptyList(),
    val contradictions: List<EvidenceContradiction> = emptyList(),
    val rejected: List<String> = emptyList(),
)

@Serializable
data class ClaimCitation(
    val claim: String,
    val supported: Boolean,
    val hits: List<EvidenceHit> = emptyList(),
)

@Serializable
data class EvidenceContradiction(
    val subject: String,
    val a: String,
    val b: String,
    val reason: String,
)
