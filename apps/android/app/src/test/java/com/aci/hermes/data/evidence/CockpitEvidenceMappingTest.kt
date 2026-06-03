package com.aci.hermes.data.evidence

import com.aci.hermes.data.cockpit.CockpitClaimCitation
import com.aci.hermes.data.cockpit.CockpitEvidenceContradiction
import com.aci.hermes.data.cockpit.CockpitEvidenceCard
import com.aci.hermes.data.cockpit.CockpitEvidenceHit
import com.aci.hermes.data.cockpit.CockpitEvidenceVerifyResult
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** The wire→domain mapping is honest: unknown trust → UNVERIFIED, ISO parsed. */
class CockpitEvidenceMappingTest {

    @Test
    fun `card maps trust and timestamps`() {
        val card = CockpitEvidenceCard(
            id = "e1",
            title = "vLLM",
            sourceUri = "https://docs.vllm.ai",
            sourceType = "official_doc",
            evidenceStrength = "primary",
            trust = "primary",
            excerpt = "uses continuous batching",
            retrievedAt = "2026-05-30T12:00:00+00:00",
            freshnessDue = "2026-08-30T12:00:00+00:00",
            citationAnchors = listOf("serving.md:12"),
        )
        val item = card.toDomain()
        assertEquals(EvidenceTrust.PRIMARY, item.trust)
        assertEquals("serving.md:12", item.citationAnchors.first())
        assertTrue(item.retrievedAt != null && item.retrievedAt!! > 0)
    }

    @Test
    fun `unknown trust maps to unverified`() {
        val item = CockpitEvidenceCard(id = "e2", trust = "wild-guess").toDomain()
        assertEquals(EvidenceTrust.UNVERIFIED, item.trust)
    }

    @Test
    fun `verify result maps citations contradictions and uncertain`() {
        val wire = CockpitEvidenceVerifyResult(
            citations = listOf(
                CockpitClaimCitation(
                    claim = "vLLM batches",
                    supported = true,
                    hits = listOf(CockpitEvidenceHit(kind = "vault", trust = "primary", title = "vLLM")),
                ),
            ),
            uncertain = listOf("Mars has two moons"),
            contradictions = listOf(CockpitEvidenceContradiction(subject = "batching", a = "u1", b = "u2", reason = "conflict")),
            rejected = listOf("api_key=sk-..."),
        )
        val v = wire.toDomain()
        assertTrue(v.citations.first().supported)
        assertEquals(EvidenceTrust.PRIMARY, v.citations.first().hits.first().trust)
        assertEquals("Mars has two moons", v.uncertain.first())
        assertEquals("batching", v.contradictions.first().subject)
        assertFalse(v.rejected.isEmpty())
    }
}
