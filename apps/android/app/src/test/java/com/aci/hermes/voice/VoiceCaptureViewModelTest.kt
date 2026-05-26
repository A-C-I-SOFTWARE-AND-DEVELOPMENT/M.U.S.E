package com.aci.hermes.voice

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * Unit tests for [VoiceCaptureViewModel]. Uses [UnconfinedTestDispatcher]
 * so the recognizer-event collector subscribes inline during VM
 * construction — otherwise `MutableSharedFlow(replay=0)` would drop
 * events emitted before the test's first `advanceUntilIdle()`.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class VoiceCaptureViewModelTest {

    private lateinit var recognizer: FakeVoiceRecognizer
    private lateinit var router: RecordingRouter
    private lateinit var dispatcher: UnconfinedTestDispatcher
    private lateinit var workScope: CoroutineScope
    private lateinit var viewModel: VoiceCaptureViewModel

    @Before fun setUp() {
        recognizer = FakeVoiceRecognizer(isAvailable = true)
        router = RecordingRouter()
        dispatcher = UnconfinedTestDispatcher()
        workScope = TestScope(dispatcher)
        viewModel = VoiceCaptureViewModel(
            recognizer = recognizer,
            router = router,
            scope = workScope,
        )
    }

    @After fun tearDown() {
        viewModel.dispose()
    }

    @Test fun `mic is not opened on construction`() = runTest {
        // No call to acknowledgeEducation()/onPermissionResult() yet.
        assertEquals(0, recognizer.startCount)
        assertEquals(0, recognizer.cancelCount)
        assertEquals(VoiceCaptureStep.Idle, viewModel.state.value.step)
    }

    @Test fun `open shows education first not permission request`() {
        viewModel.open()
        assertEquals(VoiceCaptureStep.Education, viewModel.state.value.step)
        assertEquals(0, recognizer.startCount)
    }

    @Test fun `acknowledge education advances to requesting permission`() {
        viewModel.open()
        viewModel.acknowledgeEducation()
        assertEquals(VoiceCaptureStep.RequestingPermission, viewModel.state.value.step)
        // Permission is requested by the Compose layer, not by the VM —
        // so the recognizer must still not have been started.
        assertEquals(0, recognizer.startCount)
    }

    @Test fun `permission denied transitions to denied state without listening`() {
        viewModel.open()
        viewModel.acknowledgeEducation()
        viewModel.onPermissionResult(granted = false, permanentlyDenied = false)
        assertEquals(VoiceCaptureStep.PermissionDenied, viewModel.state.value.step)
        assertEquals(0, recognizer.startCount)
        assertFalse(viewModel.state.value.permissionPermanentlyDenied)
    }

    @Test fun `permission permanently denied is reflected in state`() {
        viewModel.open()
        viewModel.acknowledgeEducation()
        viewModel.onPermissionResult(granted = false, permanentlyDenied = true)
        assertTrue(viewModel.state.value.permissionPermanentlyDenied)
    }

    @Test fun `permission granted transitions to listening and starts recognizer`() {
        viewModel.open()
        viewModel.acknowledgeEducation()
        viewModel.onPermissionResult(granted = true)
        assertEquals(VoiceCaptureStep.Listening, viewModel.state.value.step)
        assertEquals(1, recognizer.startCount)
    }

    @Test fun `cancel from listening aborts recognizer and resets state`() {
        viewModel.open()
        viewModel.acknowledgeEducation()
        viewModel.onPermissionResult(granted = true)
        viewModel.cancel()
        assertEquals(1, recognizer.cancelCount)
        assertTrue(viewModel.state.value.dismiss)
    }

    @Test fun `stop forwards to recognizer only when listening`() {
        viewModel.open()
        viewModel.acknowledgeEducation()
        viewModel.stop()
        assertEquals(0, recognizer.stopCount)
        viewModel.onPermissionResult(granted = true)
        viewModel.stop()
        assertEquals(1, recognizer.stopCount)
    }

    @Test fun `partial transcript is shown while listening`() {
        viewModel.open()
        viewModel.acknowledgeEducation()
        viewModel.onPermissionResult(granted = true)
        recognizer.emit(VoiceRecognizerEvent.Partial("write a note about"))
        assertEquals("write a note about", viewModel.state.value.partialTranscript)
    }

    @Test fun `final transcript moves to Captured and classifies as safe`() {
        viewModel.open()
        viewModel.acknowledgeEducation()
        viewModel.onPermissionResult(granted = true)
        recognizer.emit(VoiceRecognizerEvent.Final("write a note about the cockpit redesign"))
        val state = viewModel.state.value
        assertEquals(VoiceCaptureStep.Captured, state.step)
        assertEquals("write a note about the cockpit redesign", state.finalTranscript)
        assertEquals(VoiceCommandCategory.SAFE_TEXT, state.classification?.category)
    }

    @Test fun `final transcript with serious verb marks approval-required`() {
        viewModel.open()
        viewModel.acknowledgeEducation()
        viewModel.onPermissionResult(granted = true)
        recognizer.emit(VoiceRecognizerEvent.Final("delete the production database"))
        val state = viewModel.state.value
        assertEquals(VoiceCaptureStep.Captured, state.step)
        assertEquals(VoiceCommandCategory.APPROVAL_REQUIRED, state.classification?.category)
        // CRITICAL: no routing has occurred — vague/serious commands do not
        // auto-execute. They sit at Captured for the user to decide.
        assertTrue(router.calls.isEmpty())
    }

    @Test fun `send to chat routes through router`() {
        viewModel.open()
        viewModel.acknowledgeEducation()
        viewModel.onPermissionResult(granted = true)
        recognizer.emit(VoiceRecognizerEvent.Final("draft a status update for the team"))
        viewModel.sendToChat()
        assertEquals(1, router.calls.size)
        val call = router.calls.first()
        assertEquals(RecordingRouter.Kind.SEND_TO_CHAT, call.kind)
        assertEquals(VoiceCommandCategory.SAFE_TEXT, call.classification.category)
        assertTrue(viewModel.state.value.dismiss)
    }

    @Test fun `create task routes through router and preserves classification`() {
        viewModel.open()
        viewModel.acknowledgeEducation()
        viewModel.onPermissionResult(granted = true)
        recognizer.emit(VoiceRecognizerEvent.Final("merge the open PR right now"))
        viewModel.createTask()
        assertEquals(1, router.calls.size)
        val call = router.calls.first()
        assertEquals(RecordingRouter.Kind.CREATE_TASK, call.kind)
        assertEquals(VoiceCommandCategory.APPROVAL_REQUIRED, call.classification.category)
    }

    @Test fun `send to chat is a no-op when transcript is blank`() {
        viewModel.open()
        viewModel.acknowledgeEducation()
        viewModel.onPermissionResult(granted = true)
        viewModel.sendToChat()
        assertTrue(router.calls.isEmpty())
    }

    @Test fun `editing transcript reclassifies`() {
        viewModel.open()
        viewModel.acknowledgeEducation()
        viewModel.onPermissionResult(granted = true)
        recognizer.emit(VoiceRecognizerEvent.Final("draft a polite reply"))
        assertEquals(VoiceCommandCategory.SAFE_TEXT, viewModel.state.value.classification?.category)
        viewModel.editTranscript("publish the breaking change announcement")
        assertEquals(VoiceCommandCategory.APPROVAL_REQUIRED, viewModel.state.value.classification?.category)
    }

    @Test fun `manual entry available when recognizer is not`() {
        val offlineRecognizer = FakeVoiceRecognizer(isAvailable = false)
        val offlineScope = TestScope(dispatcher)
        val vm = VoiceCaptureViewModel(
            recognizer = offlineRecognizer,
            router = router,
            scope = offlineScope,
        )
        try {
            vm.open()
            vm.acknowledgeEducation()
            assertEquals(VoiceCaptureStep.ManualEntry, vm.state.value.step)
            assertEquals(0, offlineRecognizer.startCount)
            vm.setManualTranscript("organize my Tuesday inbox")
            vm.acceptCapturedTranscript()
            assertEquals(VoiceCaptureStep.Captured, vm.state.value.step)
            assertEquals(VoiceCommandCategory.SAFE_TEXT, vm.state.value.classification?.category)
        } finally {
            vm.dispose()
        }
    }

    @Test fun `cancel phrase in final transcript dismisses sheet`() {
        viewModel.open()
        viewModel.acknowledgeEducation()
        viewModel.onPermissionResult(granted = true)
        recognizer.emit(VoiceRecognizerEvent.Final("never mind"))
        assertEquals(1, recognizer.cancelCount)
        assertTrue(viewModel.state.value.dismiss)
        assertNull(viewModel.state.value.classification)
    }

    @Test fun `recognizer error surfaces error step`() {
        viewModel.open()
        viewModel.acknowledgeEducation()
        viewModel.onPermissionResult(granted = true)
        recognizer.emit(VoiceRecognizerEvent.Error("Network timeout"))
        val step = viewModel.state.value.step
        assertTrue("Expected Error step, got $step", step is VoiceCaptureStep.Error)
        assertEquals("Network timeout", (step as VoiceCaptureStep.Error).message)
        assertNotNull(viewModel.state.value.message)
    }
}
