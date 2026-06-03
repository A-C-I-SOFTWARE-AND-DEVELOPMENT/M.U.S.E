package com.aci.hermes.data.jarvis

import com.aci.hermes.data.model.HermesTask
import com.aci.hermes.data.model.TargetTool
import com.aci.hermes.data.model.TaskStatus
import com.aci.hermes.data.model.TaskType
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class JarvisHomeStateDeriverTest {

    private fun task(
        id: String = "t1",
        title: String = "Wire up the dashboard",
        status: TaskStatus = TaskStatus.DRAFT,
        type: TaskType = TaskType.BUILD,
        target: TargetTool = TargetTool.CODEX,
        updatedAt: Long = 1_000L,
        review: String? = null,
    ) = HermesTask(
        id = id,
        title = title,
        description = "",
        status = status,
        taskType = type,
        targetTool = target,
        updatedAt = updatedAt,
        reviewNotes = review,
    )

    private fun inputs(
        running: Boolean = true,
        tasks: List<HermesTask> = emptyList(),
        local: Boolean = false,
        emergency: Boolean = false,
        transient: JarvisPresence? = null,
        now: Long = 10_000L,
    ) = JarvisHomeInputs(
        serviceRunning = running,
        tasks = tasks,
        localOnlyMode = local,
        emergencyStopActive = emergency,
        transientPresence = transient,
        nowMs = now,
    )

    // ---- presence ---------------------------------------------------------

    @Test fun `idle state renders when service running and nothing to do`() {
        val state = JarvisHomeStateDeriver.derive(inputs(running = true))
        assertEquals(JarvisPresence.IDLE, state.presence)
        assertNull(state.activeTask)
        assertTrue(state.pendingApprovals.isEmpty())
    }

    @Test fun `working state renders when an active task exists`() {
        val state = JarvisHomeStateDeriver.derive(
            inputs(tasks = listOf(task(status = TaskStatus.HANDED_TO_CODEX)))
        )
        assertEquals(JarvisPresence.WORKING, state.presence)
        assertEquals("t1", state.activeTask?.taskId)
    }

    @Test fun `pending approval state renders when a task needs review`() {
        val state = JarvisHomeStateDeriver.derive(
            inputs(tasks = listOf(task(status = TaskStatus.READY_FOR_HANDOFF)))
        )
        assertEquals(JarvisPresence.WAITING_FOR_APPROVAL, state.presence)
        assertEquals(1, state.pendingApprovals.size)
    }

    @Test fun `serious action pending escalates over plain approval`() {
        val state = JarvisHomeStateDeriver.derive(
            inputs(tasks = listOf(task(status = TaskStatus.NEEDS_REVISION, type = TaskType.BUILD)))
        )
        assertEquals(JarvisPresence.SERIOUS_ACTION_PENDING, state.presence)
        assertEquals(ApprovalRisk.SERIOUS, state.pendingApprovals.single().risk)
    }

    @Test fun `critical state renders when an audit needs revision`() {
        val state = JarvisHomeStateDeriver.derive(
            inputs(tasks = listOf(task(status = TaskStatus.NEEDS_REVISION, type = TaskType.AUDIT)))
        )
        assertEquals(JarvisPresence.CRITICAL_ACTION_PENDING, state.presence)
        assertTrue(state.hasCriticalApproval)
    }

    @Test fun `gateway disconnected state renders when service stopped`() {
        val state = JarvisHomeStateDeriver.derive(inputs(running = false))
        assertEquals(JarvisPresence.SERVICE_STOPPED, state.presence)
        assertEquals(GatewayStatus.DISCONNECTED, state.gateway)
    }

    @Test fun `service stopped is preferred over gateway when nothing pending`() {
        val state = JarvisHomeStateDeriver.derive(inputs(running = false, local = true))
        assertEquals(JarvisPresence.SERVICE_STOPPED, state.presence)
        assertEquals(GatewayStatus.DISCONNECTED, state.gateway)
    }

    @Test fun `emergency stop active wins over every other signal`() {
        val state = JarvisHomeStateDeriver.derive(
            inputs(
                emergency = true,
                tasks = listOf(task(status = TaskStatus.NEEDS_REVISION, type = TaskType.AUDIT)),
            )
        )
        assertEquals(JarvisPresence.EMERGENCY_STOP_ACTIVE, state.presence)
        assertTrue(state.emergencyStopActive)
    }

    @Test fun `offline mock mode renders when local only and idle`() {
        val state = JarvisHomeStateDeriver.derive(inputs(local = true))
        assertEquals(JarvisPresence.OFFLINE_MOCK, state.presence)
        assertEquals(GatewayStatus.DEGRADED, state.gateway)
        assertTrue(state.mockMode)
    }

    @Test fun `listening transient is honored only when no higher block`() {
        val listening = JarvisHomeStateDeriver.derive(
            inputs(transient = JarvisPresence.LISTENING)
        )
        assertEquals(JarvisPresence.LISTENING, listening.presence)

        val critical = JarvisHomeStateDeriver.derive(
            inputs(
                transient = JarvisPresence.LISTENING,
                tasks = listOf(task(status = TaskStatus.NEEDS_REVISION, type = TaskType.AUDIT)),
            )
        )
        assertEquals(JarvisPresence.CRITICAL_ACTION_PENDING, critical.presence)
    }

    @Test fun `thinking transient is honored when idle`() {
        val state = JarvisHomeStateDeriver.derive(
            inputs(transient = JarvisPresence.THINKING)
        )
        assertEquals(JarvisPresence.THINKING, state.presence)
    }

    // ---- emergency stop visible ------------------------------------------

    @Test fun `emergency stop is always visible (button derived from settings)`() {
        // The button is rendered unconditionally by the screen; this test
        // documents that the state carries enough info for it.
        val on = JarvisHomeStateDeriver.derive(inputs(emergency = true))
        assertTrue(on.emergencyStopActive)
        val off = JarvisHomeStateDeriver.derive(inputs(emergency = false))
        assertFalse(off.emergencyStopActive)
    }

    // ---- navigation contracts (suggested actions) ------------------------

    @Test fun `navigation action - emergency stop suggests deactivation`() {
        val state = JarvisHomeStateDeriver.derive(inputs(emergency = true))
        assertEquals(SuggestedKind.DEACTIVATE_EMERGENCY_STOP, state.suggestedNextAction?.kind)
    }

    @Test fun `navigation action - stopped service suggests start`() {
        val state = JarvisHomeStateDeriver.derive(inputs(running = false))
        assertEquals(SuggestedKind.START_SERVICE, state.suggestedNextAction?.kind)
    }

    @Test fun `navigation action - critical approval routes to approvals`() {
        val state = JarvisHomeStateDeriver.derive(
            inputs(tasks = listOf(task(status = TaskStatus.NEEDS_REVISION, type = TaskType.AUDIT)))
        )
        val suggested = state.suggestedNextAction
        assertNotNull(suggested)
        assertEquals(SuggestedKind.OPEN_APPROVAL, suggested!!.kind)
        assertEquals("t1", suggested.taskId)
    }

    @Test fun `navigation action - active task routes to tasks`() {
        val state = JarvisHomeStateDeriver.derive(
            inputs(tasks = listOf(task(status = TaskStatus.IN_REVIEW)))
        )
        val suggested = state.suggestedNextAction
        assertNotNull(suggested)
        assertEquals(SuggestedKind.OPEN_ACTIVE_TASK, suggested!!.kind)
        assertEquals("t1", suggested.taskId)
    }

    @Test fun `navigation action - idle suggests chat`() {
        val state = JarvisHomeStateDeriver.derive(inputs())
        assertEquals(SuggestedKind.OPEN_CHAT, state.suggestedNextAction?.kind)
    }

    // ---- workers & memory pulse ------------------------------------------

    @Test fun `worker is busy when its task was updated within the busy window`() {
        val now = 100_000L
        val state = JarvisHomeStateDeriver.derive(
            inputs(
                now = now,
                tasks = listOf(task(target = TargetTool.CLAUDE_CODE, updatedAt = now - 60_000L)),
            )
        )
        val worker = state.workers.first { it.target == TargetTool.CLAUDE_CODE }
        assertTrue(worker.busy)
    }

    @Test fun `worker is idle when last activity outside the busy window`() {
        val now = 100_000L
        val state = JarvisHomeStateDeriver.derive(
            inputs(
                now = now,
                tasks = listOf(
                    task(
                        target = TargetTool.CLAUDE_CODE,
                        status = TaskStatus.COMPLETE,
                        updatedAt = now - 60 * 60 * 1000L,
                    )
                ),
            )
        )
        val worker = state.workers.first { it.target == TargetTool.CLAUDE_CODE }
        assertFalse(worker.busy)
    }

    @Test fun `memory pulse keeps the six most recent updates`() {
        val tasks = (1..8).map { i -> task(id = "t$i", updatedAt = i * 1_000L) }
        val state = JarvisHomeStateDeriver.derive(inputs(tasks = tasks))
        assertEquals(6, state.memoryPulse.size)
        // Most-recent first.
        assertEquals(8_000L, state.memoryPulse.first().timestamp)
    }

    @Test fun `approval reason falls back to default when review notes are blank`() {
        val state = JarvisHomeStateDeriver.derive(
            inputs(tasks = listOf(task(status = TaskStatus.NEEDS_REVISION, review = null)))
        )
        assertTrue(state.pendingApprovals.single().reason.isNotBlank())
    }

    // ---- live backend overlay --------------------------------------------

    private fun snapshot(
        runningJobs: Int = 1,
        workerId: String = "codex_cli",
        approvalTier: String = "CRITICAL",
        memoryTitle: String = "Owner prefers free-first",
    ) = com.aci.hermes.data.cockpit.CockpitHomeSnapshot(
        runtime = com.aci.hermes.data.cockpit.RuntimeStatus(
            gateway = com.aci.hermes.data.cockpit.GatewayRuntime(
                version = "0.1.0", startedAt = "t", mode = "local",
            ),
            host = com.aci.hermes.data.cockpit.HostInfo("Linux", "x86_64", "h"),
            queue = com.aci.hermes.data.cockpit.QueueSnapshot(
                running = runningJobs, queued = 0, waitingApproval = 1,
            ),
        ),
        models = com.aci.hermes.data.cockpit.ModelPolicy(
            routes = mapOf(
                "default" to com.aci.hermes.data.cockpit.ModelRoute(
                    provider = "ollama", model = "llama3", enabled = true,
                ),
            ),
            freeFirst = true,
        ),
        workers = com.aci.hermes.data.cockpit.WorkerDetectionList(
            workers = listOf(
                com.aci.hermes.data.cockpit.DetectedWorker(
                    id = workerId, displayName = "Codex", kind = "external_cli", available = true,
                ),
            ),
        ),
        jobs = com.aci.hermes.data.cockpit.JobList(
            jobs = listOf(
                com.aci.hermes.data.cockpit.CockpitJob(
                    id = "job_1", title = "Refactor", workerId = workerId, status = "RUNNING",
                    createdAt = "t", updatedAt = "t",
                ),
            ),
        ),
        approvals = com.aci.hermes.data.cockpit.CockpitApprovalCardList(
            approvals = listOf(
                com.aci.hermes.data.cockpit.CockpitApprovalCard(
                    id = "appr_1", title = "Deploy to prod", tier = approvalTier,
                    status = "PENDING", proposedAction = "push main",
                ),
            ),
        ),
        memory = com.aci.hermes.data.cockpit.CockpitMemoryList(
            items = listOf(
                com.aci.hermes.data.cockpit.CockpitMemoryItem(
                    id = "m1", category = "preference", title = memoryTitle, content = "…",
                    durability = "LONG", confidence = "HIGH",
                    provenance = com.aci.hermes.data.cockpit.CockpitMemoryProvenance(source = "chat"),
                    updatedAt = "2026-05-30T12:00:00Z",
                ),
            ),
        ),
        audit = com.aci.hermes.data.cockpit.CockpitAuditList(
            records = listOf(
                com.aci.hermes.data.cockpit.CockpitAuditRecord(
                    id = "au1", timestamp = "2026-05-30T12:00:00Z", action = "job_1 dispatched",
                    riskTier = "LOW",
                ),
            ),
        ),
        research = com.aci.hermes.data.cockpit.CockpitResearchList(
            items = listOf(
                com.aci.hermes.data.cockpit.CockpitResearchItem(
                    id = "r1", title = "Benchmark", evidenceStrength = "strong",
                    summary = "Model X tops the board",
                ),
            ),
        ),
    )

    @Test fun `live snapshot overrides local approvals jobs workers memory`() {
        val state = JarvisHomeStateDeriver.derive(
            inputs(tasks = listOf(task(status = TaskStatus.DRAFT))).copy(
                cockpit = snapshot(),
                backendSync = HomeBackendSync.LIVE,
            )
        )
        // Backend approval (CRITICAL) wins over the local DRAFT task.
        assertEquals(1, state.pendingApprovals.size)
        assertEquals(ApprovalRisk.CRITICAL, state.pendingApprovals.single().risk)
        assertEquals(JarvisPresence.CRITICAL_ACTION_PENDING, state.presence)
        // Jobs card supersedes the single local active-task card.
        assertNull(state.activeTask)
        assertEquals(1, state.cockpitJobs.size)
        assertTrue(state.cockpitJobs.single().active)
        // Worker is busy because a RUNNING job targets it.
        assertTrue(state.workers.single().busy)
        // Memory + model + audit + evidence come from the backend.
        assertEquals("preference · Owner prefers free-first", state.memoryPulse.single().label)
        assertNotNull(state.modelRouter)
        assertEquals(true, state.modelRouter?.freeFirst)
        assertEquals(1, state.auditEvents.size)
        assertEquals(1, state.evidence.size)
        assertEquals(HomeBackendSync.LIVE, state.backendSync)
        assertEquals(GatewayStatus.CONNECTED, state.gateway)
    }

    @Test fun `backend liveness implies runtime up even when local service probe is false`() {
        val state = JarvisHomeStateDeriver.derive(
            inputs(running = false).copy(cockpit = snapshot(), backendSync = HomeBackendSync.LIVE)
        )
        // Not SERVICE_STOPPED — the headless gateway is answering.
        assertEquals(JarvisPresence.CRITICAL_ACTION_PENDING, state.presence)
    }

    @Test fun `offline backend falls back to local derivation`() {
        // A non-LIVE sync must not consume the snapshot — local tasks drive UI.
        val state = JarvisHomeStateDeriver.derive(
            inputs(tasks = listOf(task(status = TaskStatus.HANDED_TO_CODEX))).copy(
                cockpit = snapshot(),
                backendSync = HomeBackendSync.OFFLINE,
                backendMessage = "unreachable",
            )
        )
        assertEquals(JarvisPresence.WORKING, state.presence)
        assertEquals("t1", state.activeTask?.taskId)
        assertTrue(state.cockpitJobs.isEmpty())
        assertEquals(HomeBackendSync.OFFLINE, state.backendSync)
        assertEquals("unreachable", state.backendMessage)
    }

    @Test fun `device capability and voice phase pass through`() {
        val cap = DeviceCapabilitySummary(headline = "Pixel · API 34", detail = "8000 MB RAM")
        val state = JarvisHomeStateDeriver.derive(
            inputs().copy(
                deviceCapability = cap,
                voicePhase = com.aci.hermes.voice.VoicePhase.LISTENING,
            )
        )
        assertEquals(cap, state.deviceCapability)
        assertEquals(com.aci.hermes.voice.VoicePhase.LISTENING, state.voicePhase)
    }
}
