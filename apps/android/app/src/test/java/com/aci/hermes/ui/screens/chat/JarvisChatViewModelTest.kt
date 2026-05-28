package com.aci.hermes.ui.screens.chat

import com.aci.hermes.data.jarvis.FakeJarvisClipboard
import com.aci.hermes.data.jarvis.FakeJarvisTaskSink
import com.aci.hermes.data.jarvis.JarvisChatChunk
import com.aci.hermes.data.jarvis.JarvisChatGateway
import com.aci.hermes.data.jarvis.JarvisChatMessage
import com.aci.hermes.data.jarvis.JarvisInlineCard
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
    ): JarvisChatViewModel = JarvisChatViewModel(
        gateway = gateway,
        taskSink = taskSink,
        logBuffer = logBuffer,
        clipboard = clipboard,
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
