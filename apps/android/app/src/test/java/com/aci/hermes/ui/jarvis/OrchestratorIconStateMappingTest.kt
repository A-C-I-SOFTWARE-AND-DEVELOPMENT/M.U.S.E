package com.aci.hermes.ui.jarvis

import com.aci.hermes.data.model.HermesTask
import com.aci.hermes.data.model.TaskStatus
import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * Verifies the orchestrator-domain → icon-domain bridge. Pure logic,
 * no Android dependencies.
 */
class OrchestratorIconStateMappingTest {

    @Test
    fun `service stopped maps to offline regardless of tasks`() {
        val inputs = OrchestratorIconStateMapping.inputsFor(
            serviceRunning = false,
            tasks = listOf(task(TaskStatus.IN_REVIEW)),
        )
        assertEquals(IconState.OFFLINE, IconStateMapper.map(inputs))
    }

    @Test
    fun `no tasks and service running maps to idle`() {
        val inputs = OrchestratorIconStateMapping.inputsFor(
            serviceRunning = true,
            tasks = emptyList(),
        )
        assertEquals(IconState.IDLE, IconStateMapper.map(inputs))
    }

    @Test
    fun `handed off task maps to working`() {
        val inputs = OrchestratorIconStateMapping.inputsFor(
            serviceRunning = true,
            tasks = listOf(task(TaskStatus.HANDED_TO_CODEX)),
        )
        assertEquals(IconState.WORKING, IconStateMapper.map(inputs))
    }

    @Test
    fun `in-review task maps to waiting for approval`() {
        val inputs = OrchestratorIconStateMapping.inputsFor(
            serviceRunning = true,
            tasks = listOf(task(TaskStatus.IN_REVIEW)),
        )
        assertEquals(IconState.WAITING_FOR_APPROVAL, IconStateMapper.map(inputs))
    }

    @Test
    fun `needs revision task surfaces warning`() {
        val inputs = OrchestratorIconStateMapping.inputsFor(
            serviceRunning = true,
            tasks = listOf(task(TaskStatus.NEEDS_REVISION)),
        )
        assertEquals(IconState.WARNING, IconStateMapper.map(inputs))
    }

    @Test
    fun `recently completed task flashes complete`() {
        val now = 1_000_000L
        val inputs = OrchestratorIconStateMapping.inputsFor(
            serviceRunning = true,
            tasks = listOf(task(TaskStatus.COMPLETE, updatedAt = now - 1_000L)),
            now = now,
        )
        assertEquals(IconState.COMPLETE, IconStateMapper.map(inputs))
    }

    @Test
    fun `older completed task does not flash`() {
        val now = 1_000_000L
        val window = OrchestratorIconStateMapping.COMPLETE_FLASH_WINDOW_MS
        val inputs = OrchestratorIconStateMapping.inputsFor(
            serviceRunning = true,
            tasks = listOf(task(TaskStatus.COMPLETE, updatedAt = now - (window + 1_000L))),
            now = now,
        )
        assertEquals(IconState.IDLE, IconStateMapper.map(inputs))
    }

    @Test
    fun `critical action overrides task-derived state`() {
        val inputs = OrchestratorIconStateMapping.inputsFor(
            serviceRunning = true,
            tasks = listOf(task(TaskStatus.HANDED_TO_CODEX)),
            criticalActionPending = true,
        )
        assertEquals(IconState.CRITICAL_ACTION_PENDING, IconStateMapper.map(inputs))
    }

    @Test
    fun `voice listening overrides working`() {
        val inputs = OrchestratorIconStateMapping.inputsFor(
            serviceRunning = true,
            tasks = listOf(task(TaskStatus.HANDED_TO_CODEX)),
            voiceListening = true,
        )
        assertEquals(IconState.LISTENING, IconStateMapper.map(inputs))
    }

    private fun task(status: TaskStatus, updatedAt: Long = 0L): HermesTask = HermesTask(
        id = "t-${status.name}",
        title = "test",
        status = status,
        updatedAt = updatedAt,
    )
}
