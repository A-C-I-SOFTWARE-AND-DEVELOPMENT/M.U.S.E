package com.aci.hermes.data.audit

import com.aci.hermes.data.model.audit.ActionResult
import com.aci.hermes.data.model.audit.ApprovalState
import com.aci.hermes.data.model.audit.AuditRecord
import com.aci.hermes.data.model.audit.EvidenceItem
import com.aci.hermes.data.model.audit.EvidenceKind
import com.aci.hermes.data.model.audit.ProofRecord
import com.aci.hermes.data.model.audit.RiskTier
import com.aci.hermes.data.model.audit.RollbackPlan
import com.aci.hermes.data.model.audit.RouteDestination
import com.aci.hermes.data.model.audit.RouteSummary
import com.aci.hermes.data.model.audit.VerificationResult
import com.aci.hermes.data.model.audit.VerificationStatus
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class AuditRepositoryTest {

    private val repository = AuditRepository()

    @Test
    fun `audit list renders with mock data`() {
        val records = repository.records.value
        assertTrue("expected mock records to seed the audit list", records.isNotEmpty())
    }

    @Test
    fun `every record has a resolvable proof`() {
        val records = repository.records.value
        records.forEach { record ->
            val proof = repository.proofSnapshot(record.id)
            assertNotNull("missing proof for ${record.id}", proof)
            assertEquals(record.id, proof!!.auditId)
        }
    }

    @Test
    fun `at least one record exposes a failed verification state`() {
        val records = repository.records.value
        val failed = records.firstOrNull {
            val proof = repository.proofSnapshot(it.id)
            proof?.verification?.status == VerificationStatus.FAILED
        }
        assertNotNull("expected at least one failed-verification record for UI", failed)
        assertTrue(
            "failed verification record must have non-empty failing checks",
            repository.proofSnapshot(failed!!.id)!!.verification.failingChecks.isNotEmpty(),
        )
    }

    @Test
    fun `serious or critical records expose approval history`() {
        val records = repository.records.value
        val serious = records.filter {
            it.riskTier == RiskTier.SERIOUS || it.riskTier == RiskTier.CRITICAL
        }
        assertTrue("seed must include serious/critical records", serious.isNotEmpty())
        serious.forEach { record ->
            val proof = repository.proofSnapshot(record.id)
            assertNotNull(proof)
            assertTrue(
                "serious/critical record ${record.id} must expose approval history",
                proof!!.approvals.isNotEmpty(),
            )
        }
    }

    @Test
    fun `critical records carry an impact report`() {
        val records = repository.records.value
        val critical = records.filter { it.riskTier == RiskTier.CRITICAL }
        assertTrue("seed must include at least one critical-tier record", critical.isNotEmpty())
        critical.forEach { record ->
            val proof = repository.proofSnapshot(record.id)
            assertNotNull("impact report missing for ${record.id}", proof!!.impactReport)
        }
    }

    @Test
    fun `secret-like values in mock data are redacted before display`() {
        repository.records.value.forEach { record ->
            assertFalse(
                "audit record ${record.id} leaked a secret",
                SecretRedactor.containsSecret(record.userRequest) ||
                    SecretRedactor.containsSecret(record.action) ||
                    SecretRedactor.containsSecret(record.route.reason),
            )
            val proof = repository.proofSnapshot(record.id)!!
            assertFalse(
                "proof ${proof.id} leaked a secret",
                SecretRedactor.containsSecret(proof.rationale) ||
                    proof.evidence.any { SecretRedactor.containsSecret(it.body) } ||
                    SecretRedactor.containsSecret(proof.impactReport),
            )
        }
    }

    @Test
    fun `injected seed with secret-bearing content is scrubbed on the way out`() {
        val ts = 1_700_000_000_000L
        val pollutedSeed = object : AuditSeed {
            override fun records(): List<AuditRecord> = listOf(
                AuditRecord(
                    id = "leak_1",
                    timestamp = ts,
                    userRequest = "set OPENAI_API_KEY=sk-proj-leakedsecret1234567890abcdefgh",
                    action = "wrote .env with TOKEN=ghp_leakedsecretabcdefghij1234567890",
                    riskTier = RiskTier.SERIOUS,
                    route = RouteSummary(
                        destination = RouteDestination.LOCAL_WORKER,
                        model = null,
                        reason = "Authorization: Bearer leakedheadervalue1234567890",
                        durationMs = 100,
                    ),
                    approvalState = ApprovalState.APPROVED,
                    result = ActionResult.SUCCESS,
                    confidence = 0.9f,
                    proofId = "leak_1_proof",
                ),
            )

            override fun proofs(): List<ProofRecord> = listOf(
                ProofRecord(
                    id = "leak_1_proof",
                    auditId = "leak_1",
                    rationale = "Note: password=hunter2-secret was in the original request.",
                    evidence = listOf(
                        EvidenceItem(
                            id = "ev",
                            kind = EvidenceKind.LOG,
                            title = "deploy log",
                            body = "exported AWS_SECRET_ACCESS_KEY=AKIAIOSFODNN7EXAMPLEKEY",
                        ),
                    ),
                    testsRun = emptyList(),
                    filesChanged = emptyList(),
                    verification = VerificationResult(
                        status = VerificationStatus.PASSED,
                        summary = "OK with token=leakedsummaryvalueXXXXXXX",
                        failingChecks = emptyList(),
                        passedChecks = emptyList(),
                    ),
                    approvals = emptyList(),
                    rollback = RollbackPlan(
                        id = "rb",
                        summary = "revert password=hunter2",
                        steps = listOf("git revert deadbeef"),
                        automatic = true,
                        executed = false,
                    ),
                    impactReport = "Affected secret token=ghp_anotherleakedvalue1234567890",
                    workerRuns = emptyList(),
                ),
            )
        }

        val repo = AuditRepository(seed = pollutedSeed)
        val rec = repo.records.value.single()
        val proof = repo.proofSnapshot("leak_1")!!

        assertFalse(SecretRedactor.containsSecret(rec.userRequest))
        assertFalse(SecretRedactor.containsSecret(rec.action))
        assertFalse(SecretRedactor.containsSecret(rec.route.reason))
        assertFalse(SecretRedactor.containsSecret(proof.rationale))
        assertFalse(SecretRedactor.containsSecret(proof.evidence.first().body))
        assertFalse(SecretRedactor.containsSecret(proof.verification.summary))
        assertFalse(SecretRedactor.containsSecret(proof.rollback!!.summary))
        assertFalse(SecretRedactor.containsSecret(proof.impactReport))
    }

    @Test
    fun `proofSnapshot returns null for unknown id`() {
        assertNull(repository.proofSnapshot("does-not-exist"))
    }
}
