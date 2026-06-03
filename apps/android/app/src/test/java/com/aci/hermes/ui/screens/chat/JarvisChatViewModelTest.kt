package com.aci.hermes.ui.screens.chat

import com.aci.hermes.data.jarvis.FakeJarvisApprovalGateway
import com.aci.hermes.data.jarvis.FakeJarvisClipboard
import com.aci.hermes.data.jarvis.FakeJarvisJobDispatcher
import com.aci.hermes.data.jarvis.FakeJarvisRecordInspector
import com.aci.hermes.data.jarvis.FakeJarvisTaskSink
import com.aci.hermes.data.jarvis.JarvisApprovalResult
import com.aci.hermes.data.jarvis.JarvisChatChunk
import com.aci.hermes.data.jarvis.JarvisChatGateway
import com.aci.hermes.data.jarvis.JarvisChatMessage
import com.aci.hermes.data.jarvis.JarvisDispatchResult
import com.aci.hermes.data.jarvis.JarvisInlineCard
import com.aci.hermes.data.jarvis.JarvisPhase
import com.aci.hermes.data.jarvis.JarvisRecordRef
import com.aci.hermes.data.jarvis.JarvisToolStatus
import com.aci.hermes.data.jarvis.JarvisTone
import com.aci.hermes.data.jarvis.MockJarvisChatGateway
import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class JarvisChatViewModelTest {

    private val testDispatcher = StandardTestDispatcher()
    private val logBuffer = LogBuffer()

    @Before
    fun setUp() {
        Dispatchers.setMain(testDispatcher)
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    private fun newViewModel(
        gateway: JarvisChatGateway = MockJarvisChatGateway(chunkDelayMs = 0L),
        taskSink: FakeJarvisTaskSink = FakeJarvisTaskSink(),
        clipboard: FakeJarvisClipboard = FakeJarvisClipboard(),
        jobDispatcher: FakeJarvisJobDispatcher = FakeJarvisJobDispatcher(available = false),
        approvalGateway: FakeJarvisApprovalGateway = FakeJarvisApprovalGateway(available = false),
        recordInspector: FakeJarvisRecordInspector = FakeJarvisRecordInspector(available = false),
    ): JarvisChatViewModel = JarvisChatViewModel(
        gateway = gateway,
        taskSink = taskSink,
        logBuffer = logBuffer,
        clipboard = clipboard,
        jobDispatcher = jobDispatcher,
        approvalGateway = approvalGateway,
        recordInspector = recordInspector,
    )

    @Test
    fun `welcome message is present on init`() {
        val vm = newViewModel()
        val first = vm.state.value.messages.single()
        assertTrue(first is JarvisChatMessage.Jarvis)
        assertTrue((first as JarvisChatMessage.Jarvis).body.isNotBlank())
    }

    @Test
    fun `sending a casual message produces a jarvis reply`() = runTest(testDispatcher) {
        val vm = newViewModel()
        vm.onDraftChange("hi")
        vm.send()
        advanceUntilIdle()
        val replies = vm.state.value.messages.filterIsInstance<JarvisChatMessage.Jarvis>()
        assertEquals(2, replies.size) // welcome + reply
        val reply = replies.last()
        assertTrue(reply.body.isNotBlank())
        assertFalse(reply.streaming)
        assertFalse(vm.state.value.responding)
    }

    @Test
    fun `task prompt yields inline task card and promotes to sink`() = runTest(testDispatcher) {
        val sink = FakeJarvisTaskSink()
        val vm = newViewModel(taskSink = sink)
        vm.onDraftChange("build a chat screen for jarvis")
        vm.send()
        advanceUntilIdle()
        val reply = vm.state.value.messages.filterIsInstance<JarvisChatMessage.Jarvis>().last()
        val card = reply.inline.single()
        assertTrue(card is JarvisInlineCard.Task)
        vm.promoteInlineTask(reply.id, card as JarvisInlineCard.Task)
        advanceUntilIdle()
        assertEquals(1, sink.saved.size)
        assertTrue(sink.saved.single().title.isNotBlank())
    }

    @Test
    fun `approval prompt yields approval card and approve flips state`() = runTest(testDispatcher) {
        val vm = newViewModel()
        vm.onDraftChange("deploy gateway to prod")
        vm.send()
        advanceUntilIdle()
        val reply = vm.state.value.messages.filterIsInstance<JarvisChatMessage.Jarvis>().last()
        val card = reply.inline.single() as JarvisInlineCard.Approval
        assertEquals(JarvisTone.SERIOUS, reply.tone)
        vm.approveInline(reply.id, card)
        assertTrue(vm.state.value.approved.any { it.startsWith("${reply.id}/Approval") })
    }

    @Test
    fun `serious prompt yields serious card`() = runTest(testDispatcher) {
        val vm = newViewModel()
        vm.onDraftChange("review the password handling for leaks")
        vm.send()
        advanceUntilIdle()
        val reply = vm.state.value.messages.filterIsInstance<JarvisChatMessage.Jarvis>().last()
        assertTrue(reply.inline.single() is JarvisInlineCard.Serious)
    }

    @Test
    fun `critical prompt yields critical card and bad ack is rejected`() = runTest(testDispatcher) {
        val vm = newViewModel()
        vm.onDraftChange("drop table users in prod")
        vm.send()
        advanceUntilIdle()
        val reply = vm.state.value.messages.filterIsInstance<JarvisChatMessage.Jarvis>().last()
        val card = reply.inline.single() as JarvisInlineCard.Critical
        assertEquals(JarvisTone.CRITICAL, reply.tone)
        vm.ackCritical(reply.id, card, typed = "nope")
        assertFalse(vm.state.value.ackedCritical.any { it.startsWith("${reply.id}/Critical") })
        vm.ackCritical(reply.id, card, typed = card.requiredAck)
        assertTrue(vm.state.value.ackedCritical.any { it.startsWith("${reply.id}/Critical") })
    }

    @Test
    fun `expand detail toggles the expanded set`() = runTest(testDispatcher) {
        val vm = newViewModel()
        vm.onDraftChange("walk me through the architecture")
        vm.send()
        advanceUntilIdle()
        val reply = vm.state.value.messages.filterIsInstance<JarvisChatMessage.Jarvis>().last()
        assertNotNull(reply.detail)
        vm.toggleExpanded(reply.id)
        assertTrue(reply.id in vm.state.value.expanded)
        vm.toggleExpanded(reply.id)
        assertFalse(reply.id in vm.state.value.expanded)
    }

    @Test
    fun `gateway error surfaces error bubble and retry re-sends`() = runTest(testDispatcher) {
        val vm = newViewModel()
        vm.onDraftChange("/error simulate")
        vm.send()
        advanceUntilIdle()
        val errors = vm.state.value.messages.filterIsInstance<JarvisChatMessage.Error>()
        assertEquals(1, errors.size)
        vm.retry()
        advanceUntilIdle()
        val afterRetry = vm.state.value.messages.filterIsInstance<JarvisChatMessage.Error>()
        assertEquals("retry should reproduce the same failure path", 1, afterRetry.size)
    }

    @Test
    fun `stop cancels an in-flight stream`() = runTest(testDispatcher) {
        val slow = SlowGateway()
        val vm = newViewModel(gateway = slow)
        vm.onDraftChange("hello")
        vm.send()
        testDispatcher.scheduler.runCurrent()
        vm.stop()
        advanceUntilIdle()
        assertFalse(vm.state.value.responding)
    }

    @Test
    fun `copy message uses the clipboard sink`() = runTest(testDispatcher) {
        val clipboard = FakeJarvisClipboard()
        val vm = newViewModel(clipboard = clipboard)
        val welcome = vm.state.value.messages.single()
        vm.copyMessage(welcome.id)
        assertEquals(1, clipboard.writes.size)
        assertEquals("Jarvis Prime", clipboard.writes.single().first)
    }

    @Test
    fun `clear transcript resets to the welcome message`() = runTest(testDispatcher) {
        val vm = newViewModel()
        vm.onDraftChange("hi")
        vm.send()
        advanceUntilIdle()
        assertTrue(vm.state.value.messages.size > 1)
        vm.clearTranscript()
        assertEquals(1, vm.state.value.messages.size)
        assertNull(vm.state.value.snackbar)
    }

    @Test
    fun `task turn surfaces phase rail and tool calls`() = runTest(testDispatcher) {
        val vm = newViewModel()
        vm.onDraftChange("build a chat screen for jarvis")
        vm.send()
        advanceUntilIdle()
        val reply = vm.state.value.messages.filterIsInstance<JarvisChatMessage.Jarvis>().last()
        // Phase rail advanced through routing into the tool phase.
        assertTrue(reply.phases.contains(JarvisPhase.ROUTING))
        assertTrue(reply.phases.contains(JarvisPhase.TOOL))
        // Tool calls folded START+terminal into single entries (no dupes).
        assertEquals(2, reply.toolCalls.size)
        assertTrue(reply.toolCalls.all { it.status == JarvisToolStatus.OK })
        // Evidence + ledger refs are available off the reply.
        assertEquals(2, reply.records.size)
    }

    @Test
    fun `tool detail expands and collapses`() = runTest(testDispatcher) {
        val vm = newViewModel()
        vm.onDraftChange("fix the bug in the gateway")
        vm.send()
        advanceUntilIdle()
        val reply = vm.state.value.messages.filterIsInstance<JarvisChatMessage.Jarvis>().last()
        val tool = reply.toolCalls.first()
        vm.toggleToolExpanded(tool.id)
        assertTrue(tool.id in vm.state.value.expandedTools)
        vm.toggleToolExpanded(tool.id)
        assertFalse(tool.id in vm.state.value.expandedTools)
    }

    @Test
    fun `continue re-streams without adding a user message`() = runTest(testDispatcher) {
        val vm = newViewModel()
        vm.onDraftChange("hi")
        vm.send()
        advanceUntilIdle()
        val usersBefore = vm.state.value.messages.count { it is JarvisChatMessage.User }
        vm.continueReply()
        advanceUntilIdle()
        val usersAfter = vm.state.value.messages.count { it is JarvisChatMessage.User }
        assertEquals("continue must not add a user turn", usersBefore, usersAfter)
        assertFalse(vm.state.value.responding)
    }

    @Test
    fun `createJob dispatches to cockpit when paired`() = runTest(testDispatcher) {
        val dispatcher = FakeJarvisJobDispatcher(available = true, result = JarvisDispatchResult.Ok("job_42"))
        val vm = newViewModel(jobDispatcher = dispatcher)
        vm.onDraftChange("build a chat screen for jarvis")
        vm.send()
        advanceUntilIdle()
        val reply = vm.state.value.messages.filterIsInstance<JarvisChatMessage.Jarvis>().last()
        vm.createJob(reply.id)
        advanceUntilIdle()
        assertEquals(1, dispatcher.calls.size)
        assertTrue(vm.state.value.snackbar?.contains("job_42") == true)
    }

    @Test
    fun `createJob falls back to local draft when unpaired`() = runTest(testDispatcher) {
        val sink = FakeJarvisTaskSink()
        val dispatcher = FakeJarvisJobDispatcher(available = false)
        val vm = newViewModel(taskSink = sink, jobDispatcher = dispatcher)
        vm.onDraftChange("build a chat screen for jarvis")
        vm.send()
        advanceUntilIdle()
        val reply = vm.state.value.messages.filterIsInstance<JarvisChatMessage.Jarvis>().last()
        vm.createJob(reply.id)
        advanceUntilIdle()
        assertEquals("unpaired dispatch must not call the cockpit", 0, dispatcher.calls.size)
        assertEquals(1, sink.saved.size)
    }

    @Test
    fun `approve with live id submits to the gateway`() = runTest(testDispatcher) {
        val approvals = FakeJarvisApprovalGateway(available = true, result = JarvisApprovalResult.Accepted)
        val vm = newViewModel(approvalGateway = approvals)
        val msgId = "m1"
        val card = JarvisInlineCard.Approval(
            title = "Deploy",
            summary = "ship it",
            impact = "prod",
            approvalId = "appr-7",
        )
        vm.approveInline(msgId, card)
        advanceUntilIdle()
        assertEquals(listOf("appr-7"), approvals.approvedIds)
        assertTrue(vm.state.value.approved.any { it.startsWith("$msgId/Approval") })
    }

    @Test
    fun `approve without live id stays local`() = runTest(testDispatcher) {
        val approvals = FakeJarvisApprovalGateway(available = true)
        val vm = newViewModel(approvalGateway = approvals)
        val card = JarvisInlineCard.Approval(title = "x", summary = "y", impact = "z") // approvalId null
        vm.approveInline("m1", card)
        advanceUntilIdle()
        assertTrue("local-only approval must not hit the gateway", approvals.approvedIds.isEmpty())
    }

    @Test
    fun `gateway rejection rolls back the optimistic approval`() = runTest(testDispatcher) {
        val approvals = FakeJarvisApprovalGateway(
            available = true,
            result = JarvisApprovalResult.Rejected("phrase required"),
        )
        val vm = newViewModel(approvalGateway = approvals)
        val card = JarvisInlineCard.Approval(title = "x", summary = "y", impact = "z", approvalId = "a1")
        vm.approveInline("m1", card)
        advanceUntilIdle()
        assertFalse(
            "a declined gateway approval must not leave the card approved",
            vm.state.value.approved.any { it.startsWith("m1/Approval") },
        )
    }

    @Test
    fun `inspectRecord loads a view when an inspector is available`() = runTest(testDispatcher) {
        val inspector = FakeJarvisRecordInspector(available = true)
        val vm = newViewModel(recordInspector = inspector)
        vm.inspectRecord(JarvisRecordRef("aud-1", "Evidence", JarvisRecordRef.Kind.EVIDENCE))
        advanceUntilIdle()
        assertEquals(1, inspector.loaded.size)
        assertNotNull(vm.state.value.recordSheet)
        vm.dismissRecord()
        assertNull(vm.state.value.recordSheet)
    }

    @Test
    fun `inspectRecord is a no-op without an inspector`() = runTest(testDispatcher) {
        val vm = newViewModel() // recordInspector unavailable by default
        vm.inspectRecord(JarvisRecordRef("aud-1", "Evidence", JarvisRecordRef.Kind.EVIDENCE))
        advanceUntilIdle()
        assertNull(vm.state.value.recordSheet)
        assertNotNull(vm.state.value.snackbar)
    }

    /** Gateway that emits one Body chunk after a delay, used to test abort. */
    private class SlowGateway : JarvisChatGateway {
        override val displayName: String = "slow-test"
        override val supportsStreaming: Boolean = true
        override fun send(history: List<JarvisChatMessage>, prompt: String): Flow<JarvisChatChunk> = flow {
            emit(JarvisChatChunk.Thinking)
            delay(1_000)
            emit(JarvisChatChunk.Body("never reached"))
            emit(JarvisChatChunk.Done)
        }
    }
}
