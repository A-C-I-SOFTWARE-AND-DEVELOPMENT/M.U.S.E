package com.aci.hermes.data.orchestrator

import com.aci.hermes.data.model.ApprovalState
import com.aci.hermes.data.model.RiskTier
import com.aci.hermes.data.model.TaskStatus
import com.aci.hermes.data.model.WorkerPhase
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * Migration coverage for legacy Hermes-era envelopes (no Jarvis fields,
 * pre-rename status names). Repository load must rewrite the status enum
 * and fill the Jarvis defaults rather than dropping the task on the floor.
 */
class HermesTaskRepositoryMigrationTest {

    @Test
    fun `legacy READY_FOR_HANDOFF status maps to QUEUED`() {
        val text = """
            {"version":1,"tasks":[
              {"id":"a","title":"t","description":"d","status":"READY_FOR_HANDOFF"}
            ]}
        """.trimIndent()
        val tasks = HermesTaskRepository.decodeEnvelopeText(text)
        assertEquals(1, tasks.size)
        assertEquals(TaskStatus.QUEUED, tasks[0].status)
    }

    @Test
    fun `legacy HANDED_TO_CODEX maps to EXECUTING`() {
        val tasks = HermesTaskRepository.decodeEnvelopeText(envelopeWithStatus("HANDED_TO_CODEX"))
        assertEquals(TaskStatus.EXECUTING, tasks.single().status)
    }

    @Test
    fun `legacy HANDED_TO_CLAUDE maps to REVIEWING`() {
        val tasks = HermesTaskRepository.decodeEnvelopeText(envelopeWithStatus("HANDED_TO_CLAUDE"))
        assertEquals(TaskStatus.REVIEWING, tasks.single().status)
    }

    @Test
    fun `legacy IN_REVIEW maps to REVIEWING`() {
        val tasks = HermesTaskRepository.decodeEnvelopeText(envelopeWithStatus("IN_REVIEW"))
        assertEquals(TaskStatus.REVIEWING, tasks.single().status)
    }

    @Test
    fun `legacy NEEDS_REVISION maps to BLOCKED`() {
        val tasks = HermesTaskRepository.decodeEnvelopeText(envelopeWithStatus("NEEDS_REVISION"))
        assertEquals(TaskStatus.BLOCKED, tasks.single().status)
    }

    @Test
    fun `Jarvis fields default in even when the envelope predates them`() {
        // The envelope has only the original 2024 Hermes fields. After load,
        // the new Jarvis fields should have their declared defaults.
        val text = """
            {"version":1,"tasks":[
              {
                "id":"legacy-1","title":"old","description":"","status":"DRAFT",
                "createdAt":1,"updatedAt":2
              }
            ]}
        """.trimIndent()
        val task = HermesTaskRepository.decodeEnvelopeText(text).single()
        assertEquals(RiskTier.LOW, task.riskTier)
        assertEquals(ApprovalState.NOT_REQUIRED, task.approvalState)
        assertEquals(WorkerPhase.PLANNER, task.workerPhase)
        assertNull(task.blockedReason)
        assertNull(task.proofLink)
    }

    @Test
    fun `modern envelope passes through unchanged`() {
        val text = """
            {"version":2,"tasks":[
              {
                "id":"new-1","title":"x","description":"","status":"PLANNING",
                "createdAt":1,"updatedAt":2,
                "riskTier":"HIGH","approvalState":"PENDING","workerPhase":"NAVIGATOR",
                "blockedReason":null,"proofLink":"https://example.com/p","emergencyStopActive":true
              }
            ]}
        """.trimIndent()
        val task = HermesTaskRepository.decodeEnvelopeText(text).single()
        assertEquals(TaskStatus.PLANNING, task.status)
        assertEquals(RiskTier.HIGH, task.riskTier)
        assertEquals(ApprovalState.PENDING, task.approvalState)
        assertEquals(WorkerPhase.NAVIGATOR, task.workerPhase)
        assertEquals("https://example.com/p", task.proofLink)
        assertNotNull(task.emergencyStopActive)
    }

    @Test
    fun `corrupt envelope returns empty list rather than crashing`() {
        val tasks = HermesTaskRepository.decodeEnvelopeText("not json")
        assertEquals(0, tasks.size)
    }

    private fun envelopeWithStatus(status: String): String = """
        {"version":1,"tasks":[
          {"id":"t-$status","title":"t","description":"d","status":"$status"}
        ]}
    """.trimIndent()
}
