package com.aci.hermes.ui.screens.voice

import com.aci.hermes.data.jarvis.FakeJarvisTaskSink
import com.aci.hermes.data.model.TaskStatus
import com.aci.hermes.data.model.TaskType
import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class VoiceCaptureViewModelTest {

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
        sink: FakeJarvisTaskSink = FakeJarvisTaskSink(),
    ): VoiceCaptureViewModel = VoiceCaptureViewModel(taskSink = sink, logBuffer = logBuffer)

    @Test
    fun `transcript populates state and clears listening`() {
        val vm = newViewModel()
        vm.onListeningStart()
        assertTrue(vm.state.value.listening)
        vm.onTranscript("  add a task to ship the build  ")
        val s = vm.state.value
        assertEquals("add a task to ship the build", s.transcript)
        assertTrue(!s.listening)
        assertNull(s.error)
    }

    @Test
    fun `empty transcript surfaces an error and saves nothing`() = runTest(testDispatcher) {
        val sink = FakeJarvisTaskSink()
        val vm = newViewModel(sink)
        vm.onTranscript("   ")
        assertNotNull(vm.state.value.error)
        vm.saveAsTask()
        advanceUntilIdle()
        assertTrue("blank transcript must not create a task", sink.saved.isEmpty())
        assertNull(vm.state.value.savedTaskId)
    }

    @Test
    fun `saveAsTask promotes transcript into a draft task on the sink`() = runTest(testDispatcher) {
        val sink = FakeJarvisTaskSink()
        val vm = newViewModel(sink)
        vm.onTranscript("draft the release notes for v2")
        vm.saveAsTask()
        advanceUntilIdle()

        assertEquals(1, sink.saved.size)
        val task = sink.saved.single()
        assertEquals("draft the release notes for v2", task.description)
        assertEquals("draft the release notes for v2", task.promptBody)
        assertEquals(TaskType.PLANNING, task.taskType)
        assertEquals(TaskStatus.DRAFT, task.status)
        assertEquals(task.id, vm.state.value.savedTaskId)
        // Transcript is consumed once promoted.
        assertEquals("", vm.state.value.transcript)
    }

    @Test
    fun `long transcript yields a truncated title but full description`() = runTest(testDispatcher) {
        val sink = FakeJarvisTaskSink()
        val vm = newViewModel(sink)
        val long = "a".repeat(120)
        vm.onTranscript(long)
        vm.saveAsTask()
        advanceUntilIdle()

        val task = sink.saved.single()
        assertTrue("title should be capped", task.title.length <= 61) // 60 + ellipsis
        assertTrue(task.title.endsWith("…"))
        assertEquals(long, task.description)
    }

    @Test
    fun `consumeSavedTask clears the navigation signal`() = runTest(testDispatcher) {
        val vm = newViewModel()
        vm.onTranscript("ping the team")
        vm.saveAsTask()
        advanceUntilIdle()
        assertNotNull(vm.state.value.savedTaskId)
        vm.consumeSavedTask()
        assertNull(vm.state.value.savedTaskId)
    }

    @Test
    fun `recognizer unavailable surfaces an error and stops listening`() {
        val vm = newViewModel()
        vm.onListeningStart()
        vm.onRecognizerUnavailable()
        assertTrue(!vm.state.value.listening)
        assertNotNull(vm.state.value.error)
    }

    @Test
    fun `cancelling listening stops cleanly with no transcript or error`() {
        val vm = newViewModel()
        vm.onListeningStart()
        assertTrue(vm.state.value.listening)
        vm.onListeningCancelled()
        val s = vm.state.value
        assertTrue("cancel must stop listening", !s.listening)
        assertNull("cancel is not an error", s.error)
        assertEquals("", s.transcript)
    }
}
