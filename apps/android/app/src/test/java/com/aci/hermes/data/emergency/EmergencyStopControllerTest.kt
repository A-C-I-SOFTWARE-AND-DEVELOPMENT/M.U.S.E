package com.aci.hermes.data.emergency

import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.util.concurrent.atomic.AtomicLong

/**
 * State-machine tests for the emergency stop. These are the launch
 * gate's proof that the engaged → escalated → resumed path can only
 * exit through the approval flow.
 *
 * Coroutines are run with [runBlocking] (core only) so the test stays
 * robust to drift in the kotlinx-coroutines-test artifact.
 */
class EmergencyStopControllerTest {

    @get:Rule
    val tmp = TemporaryFolder()

    private val clock = AtomicLong(1_000L)
    private val ids = AtomicLong(0)
    private val log = LogBuffer()

    private lateinit var repo: EmergencyStopRepository
    private lateinit var controller: EmergencyStopController

    @Before
    fun setUp() {
        repo = EmergencyStopRepository(tmp.newFolder("emergency"))
        controller = EmergencyStopController(
            repository = repo,
            logBuffer = log,
            clock = { clock.getAndAdd(1L) },
            idGenerator = { "approval-${ids.incrementAndGet()}" },
        )
    }

    @Test
    fun engage_from_inactive_sets_soft_pause_and_audits_engage() = runBlocking {
        controller.engage(source = "ui", reason = "user tap")

        assertEquals(EmergencyStopState.SOFT_PAUSE, controller.state.value)
        val events = controller.audit.value
        assertEquals(1, events.size)
        val e = events.single()
        assertEquals(EmergencyStopAuditEvent.EventType.ENGAGE, e.type)
        assertEquals(EmergencyStopState.INACTIVE, e.from)
        assertEquals(EmergencyStopState.SOFT_PAUSE, e.to)
        assertEquals("ui", e.source)
        assertEquals("user tap", e.reason)
    }

    @Test
    fun engage_is_noop_when_already_at_higher_level() = runBlocking {
        controller.engage(source = "ui", target = EmergencyStopState.HARD_STOP)
        val beforeCount = controller.audit.value.size

        controller.engage(source = "ui", target = EmergencyStopState.SOFT_PAUSE)

        assertEquals(EmergencyStopState.HARD_STOP, controller.state.value)
        assertEquals(beforeCount, controller.audit.value.size)
    }

    @Test
    fun escalate_must_be_strictly_higher() = runBlocking {
        controller.engage(source = "ui", target = EmergencyStopState.HARD_STOP)

        val sideways = controller.escalate(
            source = "system",
            target = EmergencyStopState.HARD_STOP,
        )
        val downward = controller.escalate(
            source = "system",
            target = EmergencyStopState.SOFT_PAUSE,
        )

        assertFalse(sideways)
        assertFalse(downward)
        assertEquals(EmergencyStopState.HARD_STOP, controller.state.value)
    }

    @Test
    fun escalate_climbs_to_lockdown_and_audits_escalation() = runBlocking {
        controller.engage(source = "ui")
        val raised = controller.escalate(
            source = "system",
            target = EmergencyStopState.LOCKDOWN,
            reason = "critical",
        )

        assertTrue(raised)
        assertEquals(EmergencyStopState.LOCKDOWN, controller.state.value)
        val last = controller.audit.value.last()
        assertEquals(EmergencyStopAuditEvent.EventType.ESCALATE, last.type)
        assertEquals(EmergencyStopState.SOFT_PAUSE, last.from)
        assertEquals(EmergencyStopState.LOCKDOWN, last.to)
    }

    @Test
    fun deescalate_cannot_go_to_inactive() = runBlocking {
        controller.engage(source = "ui", target = EmergencyStopState.LOCKDOWN)

        var threw = false
        try {
            controller.deescalate(source = "ui", target = EmergencyStopState.INACTIVE)
        } catch (e: IllegalArgumentException) {
            threw = true
            assertTrue(e.message!!.contains("requestResume"))
        }
        assertTrue("deescalate to INACTIVE must throw", threw)
        assertEquals(EmergencyStopState.LOCKDOWN, controller.state.value)
    }

    @Test
    fun deescalate_to_lower_active_level_succeeds() = runBlocking {
        controller.engage(source = "ui", target = EmergencyStopState.LOCKDOWN)
        val dropped = controller.deescalate(
            source = "ui",
            target = EmergencyStopState.SOFT_PAUSE,
        )
        assertTrue(dropped)
        assertEquals(EmergencyStopState.SOFT_PAUSE, controller.state.value)
    }

    @Test
    fun resume_only_path_is_request_then_approve() = runBlocking {
        controller.engage(source = "ui", target = EmergencyStopState.HARD_STOP)

        val approval = controller.requestResume(requestedBy = "ui", reason = "all clear")
        assertNotNull(approval)
        assertEquals(EmergencyStopState.HARD_STOP, approval!!.fromState)
        assertEquals(EmergencyStopState.HARD_STOP, controller.state.value)
        assertNotNull(controller.pendingApproval.value)

        val ok = controller.approveResume(approvalId = approval.id, approver = "owner")
        assertTrue(ok)
        assertEquals(EmergencyStopState.INACTIVE, controller.state.value)
        assertNull(controller.pendingApproval.value)

        val types = controller.audit.value.map { it.type }
        assertTrue(types.contains(EmergencyStopAuditEvent.EventType.RESUME_REQUESTED))
        assertTrue(types.contains(EmergencyStopAuditEvent.EventType.RESUME_APPROVED))
        assertTrue(types.contains(EmergencyStopAuditEvent.EventType.RESUME))
    }

    @Test
    fun stale_approval_id_is_rejected() = runBlocking {
        controller.engage(source = "ui", target = EmergencyStopState.HARD_STOP)
        controller.requestResume(requestedBy = "ui")

        val rejected = controller.approveResume(
            approvalId = "wrong-id",
            approver = "owner",
        )
        assertFalse(rejected)
        assertEquals(EmergencyStopState.HARD_STOP, controller.state.value)
    }

    @Test
    fun request_resume_while_inactive_returns_null() = runBlocking {
        assertNull(controller.requestResume(requestedBy = "ui"))
    }

    @Test
    fun deny_resume_keeps_state_and_audits_denial() = runBlocking {
        controller.engage(source = "ui", target = EmergencyStopState.LOCKDOWN)
        val approval = controller.requestResume(requestedBy = "ui")!!

        val denied = controller.denyResume(
            approvalId = approval.id,
            approver = "owner",
            reason = "not yet",
        )

        assertTrue(denied)
        assertEquals(EmergencyStopState.LOCKDOWN, controller.state.value)
        assertNull(controller.pendingApproval.value)
        val types = controller.audit.value.map { it.type }
        assertTrue(types.contains(EmergencyStopAuditEvent.EventType.RESUME_DENIED))
    }

    @Test
    fun guard_blocks_destructive_actions_at_hard_stop_and_above() = runBlocking {
        controller.engage(source = "ui", target = EmergencyStopState.HARD_STOP)

        assertFalse(controller.guard(GuardedAction.SEND, source = "ui"))
        assertFalse(controller.guard(GuardedAction.DELETE, source = "ui"))
        assertFalse(controller.guard(GuardedAction.PUSH, source = "ui"))
        assertFalse(controller.guard(GuardedAction.DEPLOY, source = "ui"))
        assertTrue(controller.guard(GuardedAction.READ, source = "ui"))
        assertTrue(controller.guard(GuardedAction.STATUS, source = "ui"))

        val blocked = controller.audit.value
            .filter { it.type == EmergencyStopAuditEvent.EventType.BLOCKED_ACTION }
        assertEquals(4, blocked.size)
    }

    @Test
    fun guard_blocks_start_task_at_soft_pause_but_allows_send() = runBlocking {
        controller.engage(source = "ui", target = EmergencyStopState.SOFT_PAUSE)

        assertFalse(controller.guard(GuardedAction.START_TASK, source = "ui"))
        // SEND only blocks at HARD_STOP and above per the contract.
        assertTrue(controller.guard(GuardedAction.SEND, source = "ui"))
    }
}
