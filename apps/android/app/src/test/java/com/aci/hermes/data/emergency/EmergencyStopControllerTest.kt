package com.aci.hermes.data.emergency

import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File
import java.util.concurrent.atomic.AtomicLong

@OptIn(ExperimentalCoroutinesApi::class)
class EmergencyStopControllerTest {

    @get:Rule val tempDir = TemporaryFolder()

    private lateinit var baseDir: File
    private lateinit var repository: EmergencyStopRepository
    private lateinit var controller: EmergencyStopController
    private val clockNow = AtomicLong(1_700_000_000_000L)
    private val idSequence = AtomicLong(1)

    @Before
    fun setUp() {
        baseDir = tempDir.newFolder("filesDir")
        repository = EmergencyStopRepository(baseDir = baseDir)
        controller = EmergencyStopController(
            repository = repository,
            logBuffer = LogBuffer(),
            clock = { clockNow.get() },
            idGenerator = { "approval-${idSequence.getAndIncrement()}" },
        )
    }

    @Test
    fun `default state is INACTIVE`() {
        assertEquals(EmergencyStopState.INACTIVE, controller.state.value)
        assertTrue(controller.audit.value.isEmpty())
        assertNull(controller.pendingApproval.value)
    }

    @Test
    fun `engage transitions to SOFT_PAUSE and logs ENGAGE`() = runTest {
        controller.engage(source = "test", reason = "drill")
        assertEquals(EmergencyStopState.SOFT_PAUSE, controller.state.value)
        val event = controller.audit.value.last()
        assertEquals(EmergencyStopAuditEvent.EventType.ENGAGE, event.type)
        assertEquals(EmergencyStopState.INACTIVE, event.from)
        assertEquals(EmergencyStopState.SOFT_PAUSE, event.to)
        assertEquals("test", event.source)
        assertEquals("drill", event.reason)
    }

    @Test
    fun `engage with higher target sets that level`() = runTest {
        controller.engage(source = "test", target = EmergencyStopState.HARD_STOP)
        assertEquals(EmergencyStopState.HARD_STOP, controller.state.value)
    }

    @Test
    fun `engage does not downgrade`() = runTest {
        controller.engage(source = "test", target = EmergencyStopState.HARD_STOP)
        controller.engage(source = "test", target = EmergencyStopState.SOFT_PAUSE)
        assertEquals(EmergencyStopState.HARD_STOP, controller.state.value)
    }

    @Test
    fun `escalate refuses to lower the level`() = runTest {
        controller.engage(source = "test", target = EmergencyStopState.HARD_STOP)
        val ok = controller.escalate(source = "test", target = EmergencyStopState.SOFT_PAUSE)
        assertFalse(ok)
        assertEquals(EmergencyStopState.HARD_STOP, controller.state.value)
    }

    @Test
    fun `escalate climbs all the way to LOCKDOWN`() = runTest {
        controller.engage(source = "test")
        controller.escalate(source = "test", target = EmergencyStopState.HARD_STOP)
        controller.escalate(source = "test", target = EmergencyStopState.LOCKDOWN)
        assertEquals(EmergencyStopState.LOCKDOWN, controller.state.value)
        val escalateEvents = controller.audit.value.filter {
            it.type == EmergencyStopAuditEvent.EventType.ESCALATE
        }
        assertEquals(2, escalateEvents.size)
    }

    @Test
    fun `deescalate step down logs DEESCALATE`() = runTest {
        controller.engage(source = "test", target = EmergencyStopState.LOCKDOWN)
        val ok = controller.deescalate(source = "test", target = EmergencyStopState.HARD_STOP)
        assertTrue(ok)
        assertEquals(EmergencyStopState.HARD_STOP, controller.state.value)
        assertEquals(
            EmergencyStopAuditEvent.EventType.DEESCALATE,
            controller.audit.value.last().type,
        )
    }

    @Test(expected = IllegalArgumentException::class)
    fun `deescalate refuses to go to INACTIVE`() {
        runBlocking {
            controller.engage(source = "test", target = EmergencyStopState.HARD_STOP)
            controller.deescalate(source = "test", target = EmergencyStopState.INACTIVE)
        }
    }

    @Test
    fun `requestResume returns null when not engaged`() = runTest {
        val approval = controller.requestResume(requestedBy = "u1")
        assertNull(approval)
        assertTrue(controller.audit.value.isEmpty())
    }

    @Test
    fun `resume requires approval`() = runTest {
        controller.engage(source = "test", target = EmergencyStopState.HARD_STOP)
        val approval = controller.requestResume(requestedBy = "u1", reason = "looks fine")
        assertNotNull(approval)
        // State is still active until approveResume runs
        assertEquals(EmergencyStopState.HARD_STOP, controller.state.value)
        // Pending approval is tracked
        assertEquals(approval, controller.pendingApproval.value)

        val ok = controller.approveResume(approval!!.id, approver = "u2")
        assertTrue(ok)
        assertEquals(EmergencyStopState.INACTIVE, controller.state.value)
        assertNull(controller.pendingApproval.value)
        val resumeEvent = controller.audit.value.find {
            it.type == EmergencyStopAuditEvent.EventType.RESUME
        }
        assertNotNull(resumeEvent)
    }

    @Test
    fun `approveResume rejects stale approval id`() = runTest {
        controller.engage(source = "test")
        controller.requestResume(requestedBy = "u1")
        val ok = controller.approveResume("not-the-right-id", approver = "u2")
        assertFalse(ok)
        assertEquals(EmergencyStopState.SOFT_PAUSE, controller.state.value)
    }

    @Test
    fun `denyResume keeps the stop engaged and logs RESUME_DENIED`() = runTest {
        controller.engage(source = "test", target = EmergencyStopState.LOCKDOWN)
        val approval = controller.requestResume(requestedBy = "u1")!!
        val ok = controller.denyResume(approval.id, approver = "u2", reason = "nope")
        assertTrue(ok)
        assertEquals(EmergencyStopState.LOCKDOWN, controller.state.value)
        assertNull(controller.pendingApproval.value)
        assertEquals(
            EmergencyStopAuditEvent.EventType.RESUME_DENIED,
            controller.audit.value.last().type,
        )
    }

    @Test
    fun `isBlocked gates by action and severity`() = runTest {
        // INACTIVE → nothing blocked
        listOf(
            GuardedAction.START_TASK, GuardedAction.SEND, GuardedAction.DELETE,
            GuardedAction.PUSH, GuardedAction.DEPLOY, GuardedAction.MUTATE,
            GuardedAction.READ, GuardedAction.STATUS,
        ).forEach { assertFalse(controller.isBlocked(it)) }

        // SOFT_PAUSE blocks START_TASK only.
        controller.engage(source = "test")
        assertTrue(controller.isBlocked(GuardedAction.START_TASK))
        assertFalse(controller.isBlocked(GuardedAction.SEND))
        assertFalse(controller.isBlocked(GuardedAction.DELETE))
        assertFalse(controller.isBlocked(GuardedAction.PUSH))
        assertFalse(controller.isBlocked(GuardedAction.DEPLOY))
        assertFalse(controller.isBlocked(GuardedAction.MUTATE))
        assertFalse(controller.isBlocked(GuardedAction.READ))
        assertFalse(controller.isBlocked(GuardedAction.STATUS))

        // HARD_STOP also blocks SEND / DELETE / PUSH / DEPLOY.
        controller.escalate(source = "test", target = EmergencyStopState.HARD_STOP)
        assertTrue(controller.isBlocked(GuardedAction.SEND))
        assertTrue(controller.isBlocked(GuardedAction.DELETE))
        assertTrue(controller.isBlocked(GuardedAction.PUSH))
        assertTrue(controller.isBlocked(GuardedAction.DEPLOY))
        assertFalse(controller.isBlocked(GuardedAction.MUTATE))
        assertFalse(controller.isBlocked(GuardedAction.READ))
        assertFalse(controller.isBlocked(GuardedAction.STATUS))

        // LOCKDOWN also blocks MUTATE. READ and STATUS still allowed.
        controller.escalate(source = "test", target = EmergencyStopState.LOCKDOWN)
        assertTrue(controller.isBlocked(GuardedAction.MUTATE))
        assertFalse(controller.isBlocked(GuardedAction.READ))
        assertFalse(controller.isBlocked(GuardedAction.STATUS))
    }

    @Test
    fun `guard audits blocked attempts`() = runTest {
        controller.engage(source = "test", target = EmergencyStopState.HARD_STOP)
        val allowed = controller.guard(GuardedAction.SEND, source = "ui:test")
        assertFalse(allowed)
        val blocked = controller.audit.value.find {
            it.type == EmergencyStopAuditEvent.EventType.BLOCKED_ACTION
        }
        assertNotNull(blocked)
        assertEquals("ui:test", blocked!!.source)
        assertTrue(blocked.reason!!.contains("SEND"))
    }

    @Test
    fun `state and audit survive process restart`() = runTest {
        controller.engage(source = "test", target = EmergencyStopState.HARD_STOP)
        val auditCountBefore = controller.audit.value.size

        // Simulate fresh process.
        val freshRepo = EmergencyStopRepository(baseDir = baseDir)
        val fresh = EmergencyStopController(
            repository = freshRepo,
            logBuffer = LogBuffer(),
            clock = { clockNow.get() },
        )
        freshRepo.load()

        assertEquals(EmergencyStopState.HARD_STOP, fresh.state.value)
        assertEquals(auditCountBefore, fresh.audit.value.size)
    }

    @Test
    fun `audit log is bounded`() = runTest {
        // Exercise the trim guard by writing far more than MAX_AUDIT_ENTRIES events.
        repeat(EmergencyStopAuditEvent.MAX_AUDIT_ENTRIES + 50) {
            controller.guard(GuardedAction.SEND, source = "spam")
        }
        // Setup: emergency must be engaged for SEND to be blocked.
        controller.engage(source = "spam-engage", target = EmergencyStopState.HARD_STOP)
        repeat(EmergencyStopAuditEvent.MAX_AUDIT_ENTRIES + 50) {
            controller.guard(GuardedAction.SEND, source = "spam-after")
        }
        assertTrue(controller.audit.value.size <= EmergencyStopAuditEvent.MAX_AUDIT_ENTRIES)
    }
}
