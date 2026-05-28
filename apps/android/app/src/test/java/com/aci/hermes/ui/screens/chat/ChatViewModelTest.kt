package com.aci.hermes.ui.screens.chat

import com.aci.hermes.data.jarvis.FakeJarvisClipboard
import com.aci.hermes.data.jarvis.FakeJarvisTaskSink
import com.aci.hermes.data.jarvis.JarvisChatChunk
import com.aci.hermes.data.jarvis.JarvisChatGateway
import com.aci.hermes.data.jarvis.JarvisChatMessage
import com.aci.hermes.data.jarvis.JarvisInlineCard
import com.aci.hermes.data.jarvis.MockJarvisChatGateway
import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class ChatViewModelTest {

    private fun newScope(): CoroutineScope =
        CoroutineScope(UnconfinedTestDispatcher() + SupervisorJob())

    private fun newVm(
        gateway: JarvisChatGateway = MockJarvisChatGateway(chunkDelayMs = 0),
        sink: FakeJarvisTaskSink = FakeJarvisTaskSink(),
        clipboard: FakeJarvisClipboard = FakeJarvisClipboard(),
        scope: CoroutineScope = newScope(),
    ): Triple<ChatViewModel, FakeJarvisTaskSink, FakeJarvisClipboard> {
        val vm = ChatViewModel(
            gateway = gateway,
            taskSink = sink,
            logBuffer = LogBuffer(),
            clipboard = clipboard,
            scopeOverride = scope,
        )
        return Triple(vm, sink, clipboard)
    }

    private fun lastJarvis(vm: ChatViewModel): JarvisChatMessage.Jarvis? =
        vm.state.value.messages.filterIsInstance<JarvisChatMessage.Jarvis>().lastOrNull()

    @Test
    fun `send produces a user bubble and a Jarvis reply`() {
        val (vm, _, _) = newVm()
        val before = vm.state.value.messages.size
        vm.onDraftChange("hi")
        vm.send()

        val msgs = vm.state.value.messages
        assertTrue("transcript grew", msgs.size > before)
        assertTrue("user bubble present", msgs.any { it is JarvisChatMessage.User && it.text == "hi" })
        val jarvis = msgs.filterIsInstance<JarvisChatMessage.Jarvis>().last()
        assertFalse("reply finished streaming", jarvis.streaming)
        assertTrue("reply body non-empty", jarvis.body.isNotBlank())
    }

    @Test
    fun `task-shaped prompt yields a Task inline card`() {
        val (vm, _, _) = newVm()
        vm.onDraftChange("build a chat screen for jarvis")
        vm.send()
        val cards = lastJarvis(vm)?.inline.orEmpty()
        assertEquals(1, cards.size)
        assertTrue(cards.first() is JarvisInlineCard.Task)
    }

    @Test
    fun `approval prompt yields an Approval inline card`() {
        val (vm, _, _) = newVm()
        vm.onDraftChange("deploy gateway to prod")
        vm.send()
        val cards = lastJarvis(vm)?.inline.orEmpty()
        assertEquals(1, cards.size)
        assertTrue(cards.first() is JarvisInlineCard.Approval)
    }

    @Test
    fun `security prompt yields a Serious inline card`() {
        val (vm, _, _) = newVm()
        vm.onDraftChange("audit the api key handling for leaks")
        vm.send()
        val cards = lastJarvis(vm)?.inline.orEmpty()
        assertEquals(1, cards.size)
        assertTrue(cards.first() is JarvisInlineCard.Serious)
    }

    @Test
    fun `destructive prompt yields a Critical inline card with ack string`() {
        val (vm, _, _) = newVm()
        vm.onDraftChange("drop table users in prod")
        vm.send()
        val cards = lastJarvis(vm)?.inline.orEmpty()
        assertEquals(1, cards.size)
        val card = cards.first() as JarvisInlineCard.Critical
        assertEquals("I understand this is irreversible", card.requiredAck)
    }

    @Test
    fun `ackCritical rejects wrong string and accepts exact match`() {
        val (vm, _, _) = newVm()
        vm.onDraftChange("drop table users in prod")
        vm.send()
        val reply = lastJarvis(vm)!!
        val card = reply.inline.filterIsInstance<JarvisInlineCard.Critical>().first()

        vm.ackCritical(reply.id, card, "not the right string")
        assertEquals("Ack string didn't match.", vm.state.value.snackbar)
        assertTrue(vm.state.value.ackedCritical.isEmpty())

        vm.consumeSnackbar()
        vm.ackCritical(reply.id, card, card.requiredAck)
        assertTrue("typed ack should register", vm.state.value.ackedCritical.isNotEmpty())
    }

    @Test
    fun `stop while streaming marks the in-flight reply aborted`() = runTest {
        // Custom gateway: emit Working + a Body chunk, then suspend forever so
        // stop() has something to cancel. Mock gateway with chunkDelayMs=0
        // collapses to instant, leaving no streaming window.
        val stalling = object : JarvisChatGateway {
            override val displayName = "stalling-test"
            override val supportsStreaming = true
            override fun send(
                history: List<JarvisChatMessage>,
                prompt: String,
            ): Flow<JarvisChatChunk> = flow {
                emit(JarvisChatChunk.Thinking)
                emit(JarvisChatChunk.Working("Running long task"))
                emit(JarvisChatChunk.Body("Working on it…"))
                awaitCancellation()
            }
        }
        val scope = CoroutineScope(UnconfinedTestDispatcher(testScheduler) + SupervisorJob())
        val (vm, _, _) = newVm(gateway = stalling, scope = scope)
        vm.onDraftChange("/stall please")
        vm.send()

        // Reply should now be promoted with a partial body and streaming=true.
        val mid = lastJarvis(vm)
        assertNotNull("Jarvis reply should be promoted before stop", mid)
        assertTrue("reply should still be streaming", mid!!.streaming)

        vm.stop()

        val after = vm.state.value.messages.filterIsInstance<JarvisChatMessage.Jarvis>().last()
        assertTrue("reply should be marked aborted", after.aborted)
        assertFalse("reply should no longer be streaming", after.streaming)
    }

    @Test
    fun `retry after gateway error replays the last prompt`() {
        val (vm, _, _) = newVm()
        vm.onDraftChange("/error simulate")
        vm.send()
        val msgs = vm.state.value.messages
        assertTrue("error bubble surfaced", msgs.last() is JarvisChatMessage.Error)
        val userCountBefore = msgs.count { it is JarvisChatMessage.User }

        vm.retry()
        val after = vm.state.value.messages
        // Same prompt resent — user-message count is unchanged (retry doesn't
        // duplicate the user bubble), but the trailing error must be cleared
        // and replaced by another reply attempt.
        assertEquals(userCountBefore, after.count { it is JarvisChatMessage.User })
        // The mock gateway returns Failure for /error every time, so we expect
        // a fresh Error bubble — but the trailing-error dropping logic means
        // there is still exactly one Error at the tail.
        assertEquals(1, after.count { it is JarvisChatMessage.Error })
    }

    @Test
    fun `copyMessage pushes body and detail to clipboard`() {
        val (vm, _, clipboard) = newVm()
        vm.onDraftChange("walk me through the architecture")
        vm.send()
        val reply = lastJarvis(vm)!!

        vm.copyMessage(reply.id)

        assertEquals(1, clipboard.writes.size)
        val (label, text) = clipboard.writes.first()
        assertEquals("Jarvis Prime", label)
        assertTrue("body included", text.contains(reply.body))
        assertTrue("detail included", reply.detail?.let { text.contains(it) } == true)
    }

    @Test
    fun `clearTranscript resets to the welcome bubble`() {
        val (vm, _, _) = newVm()
        vm.onDraftChange("hi")
        vm.send()
        assertTrue(vm.state.value.messages.size > 1)

        vm.clearTranscript()

        val msgs = vm.state.value.messages
        assertEquals(1, msgs.size)
        val welcome = msgs.first()
        assertTrue("welcome is a Jarvis bubble", welcome is JarvisChatMessage.Jarvis)
        assertTrue("welcome mentions Jarvis Prime", (welcome as JarvisChatMessage.Jarvis).body.contains("Jarvis Prime"))
        assertNull(vm.state.value.snackbar)
    }

    @Test
    fun `promoteInlineTask hands the task to the sink`() {
        val (vm, sink, _) = newVm()
        vm.onDraftChange("build a chat screen for jarvis")
        vm.send()
        val reply = lastJarvis(vm)!!
        val card = reply.inline.filterIsInstance<JarvisInlineCard.Task>().first()

        vm.promoteInlineTask(reply.id, card)

        assertEquals(1, sink.saved.size)
        assertEquals(card.title, sink.saved.first().title)
        assertTrue(vm.state.value.promotedTasks.isNotEmpty())
    }
}
