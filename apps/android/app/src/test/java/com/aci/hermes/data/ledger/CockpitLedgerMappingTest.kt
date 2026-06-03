package com.aci.hermes.data.ledger

import com.aci.hermes.data.cockpit.CockpitLedgerDiff
import com.aci.hermes.data.cockpit.CockpitLedgerEvent
import com.aci.hermes.data.cockpit.CockpitLedgerEventDetail
import com.aci.hermes.data.cockpit.CockpitLedgerEvidence
import com.aci.hermes.data.cockpit.CockpitLedgerRollback
import com.aci.hermes.data.model.audit.RiskTier
import com.aci.hermes.data.model.ledger.LedgerCategory
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class CockpitLedgerMappingTest {

    @Test
    fun `event maps category, risk and flags`() {
        val m = CockpitLedgerEvent(
            id = "job1:2",
            jobId = "job1",
            index = 2,
            timestamp = "2026-06-01T09:00:00+00:00",
            category = "WORKER_RUN",
            kind = "worker_dispatch",
            worker = "codex-execute",
            riskTier = "MODERATE",
            summary = "dispatched",
            files = listOf("src/a.py"),
            hasRollback = true,
            hasDiff = true,
        ).toDomain()

        assertEquals("job1:2", m.id)
        assertEquals(LedgerCategory.WORKER_RUN, m.category)
        assertEquals(RiskTier.MODERATE, m.riskTier)
        assertEquals("codex-execute", m.worker)
        assertEquals(listOf("src/a.py"), m.files)
        assertTrue(m.hasRollback)
        assertTrue(m.hasDiff)
    }

    @Test
    fun `unknown category falls back to LIFECYCLE`() {
        val m = CockpitLedgerEvent(id = "j:0", category = "SOMETHING_NEW", riskTier = "???").toDomain()
        assertEquals(LedgerCategory.LIFECYCLE, m.category)
        assertEquals(RiskTier.LOW, m.riskTier)
    }

    @Test
    fun `detail maps payload, evidence, diff and rollback`() {
        val m = CockpitLedgerEventDetail(
            id = "job1:3",
            jobId = "job1",
            index = 3,
            category = "DEPLOY_PUBLISH",
            kind = "publish",
            riskTier = "SERIOUS",
            payload = JsonObject(mapOf("status" to JsonPrimitive("ok"), "n" to JsonPrimitive(3))),
            evidence = listOf(CockpitLedgerEvidence("e1", "title", "body", "docs/x.md")),
            diff = CockpitLedgerDiff(body = null, files = listOf("a.py")),
            rollback = CockpitLedgerRollback("revert it", listOf("git revert")),
            rollbackAvailable = true,
        ).toDomain()

        assertEquals(LedgerCategory.DEPLOY_PUBLISH, m.category)
        assertTrue(m.payload.contains("status" to "ok"))
        assertTrue(m.payload.any { it.first == "n" && it.second == "3" })
        assertEquals("docs/x.md", m.evidence[0].sourcePath)
        assertNotNull(m.diff)
        assertEquals(listOf("a.py"), m.diff!!.files)
        assertEquals("revert it", m.rollback!!.summary)
        assertTrue(m.rollbackAvailable)
    }

    @Test
    fun `null diff and rollback stay null`() {
        val m = CockpitLedgerEventDetail(id = "j:0", diff = null, rollback = null).toDomain()
        assertNull(m.diff)
        assertNull(m.rollback)
    }
}
