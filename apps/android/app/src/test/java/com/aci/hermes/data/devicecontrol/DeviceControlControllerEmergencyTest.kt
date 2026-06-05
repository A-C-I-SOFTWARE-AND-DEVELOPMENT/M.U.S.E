package com.aci.hermes.data.devicecontrol

import androidx.test.core.app.ApplicationProvider
import com.aci.hermes.data.emergency.EmergencyStopController
import com.aci.hermes.data.emergency.EmergencyStopRepository
import com.aci.hermes.data.emergency.EmergencyStopState
import com.aci.hermes.testutil.awaitUntil
import com.aci.hermes.testutil.isolatedSettings
import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

/**
 * The unified emergency stop: device control's halt is a read-only projection
 * of the audited global [EmergencyStopController], with no device-local
 * release. Engaging the global stop from any surface halts gestures; the only
 * way back to running is the replay-protected request → approve resume.
 */
@RunWith(RobolectricTestRunner::class)
class DeviceControlControllerEmergencyTest {

    @get:Rule
    val tempFolder = TemporaryFolder()

    private fun newEmergencyController(): EmergencyStopController =
        EmergencyStopController(
            EmergencyStopRepository(tempFolder.newFolder("estop-${System.nanoTime()}")),
            LogBuffer(),
        )

    private fun newController(emergency: EmergencyStopController): DeviceControlController {
        val ctx = ApplicationProvider.getApplicationContext<android.content.Context>()
        val settings = isolatedSettings(ctx)
        // Enable device control so gesturesAllowed() hinges on the halt alone.
        runBlocking { settings.setDeviceControlEnabled(true) }
        return DeviceControlController(
            context = ctx,
            settings = settings,
            ledger = DeviceActionLedger(tempFolder.newFolder("ledger-${System.nanoTime()}")),
            logBuffer = LogBuffer(),
            emergencyStop = emergency,
        )
    }

    @Test
    fun `engaging the global stop halts gestures, approved resume restores them`() {
        val emergency = newEmergencyController()
        val controller = newController(emergency)

        awaitUntil(message = "device control becomes enabled and ungated") {
            controller.gesturesAllowed()
        }
        assertFalse("not halted before any stop", controller.halted.value)

        // Engage the audited global stop (as Home / Live / device button all do).
        runBlocking { emergency.engage(source = "test", target = EmergencyStopState.HARD_STOP) }

        awaitUntil(message = "the global stop projects onto device control") {
            controller.halted.value && !controller.gesturesAllowed()
        }

        // The only way back to running is the replay-protected approved resume.
        runBlocking {
            val approval = emergency.requestResume(requestedBy = "owner")!!
            assertTrue(emergency.approveResume(approval.id, approver = "owner"))
        }

        awaitUntil(message = "approved resume clears the device halt") {
            !controller.halted.value && controller.gesturesAllowed()
        }
    }

    @Test
    fun `a soft pause from any surface also halts device gestures`() {
        val emergency = newEmergencyController()
        val controller = newController(emergency)
        awaitUntil(message = "enabled and ungated") { controller.gesturesAllowed() }

        // Any active level — not just HARD_STOP — must drop gestures.
        runBlocking { emergency.engage(source = "test", target = EmergencyStopState.SOFT_PAUSE) }

        awaitUntil(message = "soft pause halts device control too") {
            controller.halted.value && !controller.gesturesAllowed()
        }
    }
}
