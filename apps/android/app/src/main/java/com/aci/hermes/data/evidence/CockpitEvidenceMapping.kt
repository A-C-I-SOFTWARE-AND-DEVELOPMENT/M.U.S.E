package com.aci.hermes.data.evidence

import com.aci.hermes.data.cockpit.CockpitClaimCitation
import com.aci.hermes.data.cockpit.CockpitEvidenceContradiction
import com.aci.hermes.data.cockpit.CockpitEvidenceCard
import com.aci.hermes.data.cockpit.CockpitEvidenceHit
import com.aci.hermes.data.cockpit.CockpitEvidenceVerifyResult
import com.aci.hermes.data.memory.parseIsoToMillis

/**
 * Maps the cockpit wire models to the Evidence domain models. Reuses the
 * memory module's tolerant ISO parser. No fabrication: an omitted field
 * stays empty/null, and an unrecognised trust maps to
 * [EvidenceTrust.UNVERIFIED].
 */

fun CockpitEvidenceCard.toDomain(): EvidenceItem = EvidenceItem(
    id = id,
    title = title,
    sourceUri = sourceUri,
    sourceType = sourceType,
    trust = EvidenceTrust.fromWire(trust),
    evidenceStrength = evidenceStrength,
    excerpt = excerpt,
    summary = summary,
    tags = tags,
    licenseNotes = licenseNotes,
    retrievedAt = parseIsoToMillis(retrievedAt),
    freshnessDue = parseIsoToMillis(freshnessDue),
    checksum = checksum,
    citationAnchors = citationAnchors,
    addedAt = parseIsoToMillis(addedAt),
)

fun CockpitEvidenceHit.toDomain(): EvidenceHit = EvidenceHit(
    kind = kind,
    title = title,
    uri = uri,
    excerpt = excerpt,
    trust = EvidenceTrust.fromWire(trust),
    score = score,
    artifactId = artifactId,
    citationAnchors = citationAnchors,
)

fun CockpitEvidenceVerifyResult.toDomain(): EvidenceVerification = EvidenceVerification(
    citations = citations.map { it.toDomain() },
    uncertain = uncertain,
    contradictions = contradictions.map { it.toDomain() },
    rejected = rejected,
)

fun CockpitClaimCitation.toDomain(): ClaimCitation = ClaimCitation(
    claim = claim,
    supported = supported,
    hits = hits.map { it.toDomain() },
)

fun CockpitEvidenceContradiction.toDomain(): EvidenceContradiction = EvidenceContradiction(
    subject = subject,
    a = a,
    b = b,
    reason = reason,
)
