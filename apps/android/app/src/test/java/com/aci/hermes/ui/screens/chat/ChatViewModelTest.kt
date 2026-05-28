package com.aci.hermes.ui.screens.chat

import com.aci.hermes.data.jarvis.JarvisChatMessage
import com.aci.hermes.data.jarvis.JarvisInlineCard
import com.aci.hermes.data.jarvis.MockJarvisChatGateway
import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class ChatViewModelTest {

    private val dispatcher = UnconfinedTestDispatcher()

    @Before
    fun setUp() {
        Dispatchers.setMain(dispatcher)
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    // chunkDelayMs = 0 makes the mock gateway complete synchronously under
    // the unconfined test dispatcher.
    private fun newVm() = ChatViewModel(MockJarvisChatGateway(chunkDelayMs = 0L), LogBuffer())

    @Test
    fun `send appends user message and produces a jarvis reply`() = runTest {
        val vm = newVm()
        vm.onInputChange("Hello there")
        vm.send()

        val messages = vm.state.value.messages
        assertTrue("expected a user bubble", messages.any { it is JarvisChatMessage.User })
        val reply = messages.filterIsInstance<JarvisChatMessage.Jarvis>().lastOrNull()
        assertTrue("expected a jarvis reply", reply != null)
        assertFalse("reply should not still be streaming", reply!!.streaming)
        assertFalse("stream should be finished", vm.state.value.isStreaming)
        assertEquals("input should be cleared after send", "", vm.state.value.input)
    }

    @Test
    fun `no transient indicators remain after completion`() = runTest {
        val vm = newVm()
        vm.onInputChange("Tell me something")
        vm.send()

        val messages = vm.state.value.messages
        assertFalse(messages.any { it is JarvisChatMessage.Thinking })
        assertFalse(messages.any { it is JarvisChatMessage.Working })
    }

    @Test
    fun `task shaped prompt yields a task inline card`() = runTest {
        val vm = newVm()
        vm.onInputChange("build a login screen with claude code")
        vm.send()

        val reply = vm.state.value.messages.filterIsInstance<JarvisChatMessage.Jarvis>().last()
        assertTrue(
            "task prompt should attach a Task inline card",
            reply.inline.any { it is JarvisInlineCard.Task },
        )
    }

    @Test
    fun `error trigger surfaces an error bubble with a retry hint`() = runTest {
        val vm = newVm()
        vm.onInputChange("/error please fail")
        vm.send()

        val error = vm.state.value.messages.filterIsInstance<JarvisChatMessage.Error>().lastOrNull()
        assertTrue("explicit /error prompt should produce an Error bubble", error != null)
        assertTrue("error should carry a retry hint", !error!!.retryHint.isNullOrBlank())
        assertFalse(vm.state.value.isStreaming)
    }

    @Test
    fun `retry re-sends the last prompt and produces a fresh reply`() = runTest {
        val vm = newVm()
        vm.onInputChange("what's the plan")
        vm.send()
        val firstReplyCount = vm.state.value.messages.count { it is JarvisChatMessage.Jarvis }
        assertEquals(1, firstReplyCount)

        vm.retry()

        val secondReplyCount = vm.state.value.messages.count { it is JarvisChatMessage.Jarvis }
        assertEquals("retry should add a second jarvis reply", 2, secondReplyCount)
        assertFalse(vm.state.value.isStreaming)
    }

    @Test
    fun `blank input is ignored`() = runTest {
        val vm = newVm()
        vm.onInputChange("   ")
        vm.send()
        assertTrue("blank send should not create any messages", vm.state.value.messages.isEmpty())
    }

    @Test
    fun `mic toggle flips listening state without fabricating input`() {
        val vm = newVm()
        assertFalse(vm.state.value.isListening)
        vm.onMicToggle()
        assertTrue(vm.state.value.isListening)
        assertEquals("", vm.state.value.input)
        vm.onMicToggle()
        assertFalse(vm.state.value.isListening)
    }

    @Test
    fun `snackbar consume clears it`() {
        val vm = newVm()
        assertNull(vm.state.value.snackbar)
        vm.consumeSnackbar()
        assertNull(vm.state.value.snackbar)
    }
}
