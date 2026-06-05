package com.aci.hermes.ui.screens.home

import androidx.test.core.app.ApplicationProvider
import com.aci.hermes.data.cockpit.CockpitHomeRepository
import com.aci.hermes.data.cockpit.CockpitJobsRepository
import com.aci.hermes.data.cockpit.HermesCockpitClient
import com.aci.hermes.data.emergency.EmergencyStopController
import com.aci.hermes.data.emergency.EmergencyStopRepository
import com.aci.hermes.data.jarvis.JarvisPresence
import com.aci.hermes.data.orchestrator.HermesTaskRepository
import com.aci.hermes.data.preferences.SettingsRepository
import com.aci.hermes.testutil.MainDispatcherRule
import com.aci.hermes.testutil.awaitUntil
import com.aci.hermes.testutil.isolatedSettings
import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.ExperimentalCoroutinesApi
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@OptIn(ExperimentalCoroutinesApi::class)
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [33])
class JarvisPrimeHomeViewModelTest {

    @get:Rule
    val mainDispatcherRule = MainDispatcherRule()

    private lateinit var settings: SettingsRepository

    private fun newVm(): JarvisPrimeHomeViewModel {
        val ctx = ApplicationProvider.getApplicationContext<android.content.Context>()
        // Isolated settings store → a fresh, hermetic baseline every test.
        settings = isolatedSettings(ctx)
        // Unpaired cockpit client — repos degrade to honest empty in tests.
        val client = HermesCockpitClient(endpointProvider = { "" }, tokenProvider = { null })
        return mainDispatcherRule.register(JarvisPrimeHomeViewModel(
            application = ctx as android.app.Application,
            settings = settings,
            tasksRepo = HermesTaskRepository(ctx),
            logBuffer = LogBuffer(),
            homeRepo = CockpitHomeRepository(client),
            jobsRepo = CockpitJobsRepository(client),
            emergencyController = EmergencyStopController(
                EmergencyStopRepository(java.io.File(ctx.cacheDir, "estop-${System.nanoTime()}")),
                LogBuffer(),
            ),
        ))
    }


    @Test
    fun `with no running service the home reads as service-stopped`() {
        val vm = newVm()
        awaitUntil(message = "presence derives to SERVICE_STOPPED") {
            vm.state.value.presence == JarvisPresence.SERVICE_STOPPED
        }
        assertEquals(JarvisPresence.SERVICE_STOPPED, vm.state.value.presence)
    }

    @Test
    fun `emergency stop is a hard block that overrides everything`() {
        val vm = newVm()
        awaitUntil { vm.state.value.presence == JarvisPresence.SERVICE_STOPPED }

        vm.triggerEmergencyStop()
        awaitUntil(message = "emergency stop becomes the active presence") {
            vm.state.value.presence == JarvisPresence.EMERGENCY_STOP_ACTIVE
        }

        vm.deactivateEmergencyStop()
        awaitUntil(message = "presence returns to SERVICE_STOPPED after release") {
            vm.state.value.presence == JarvisPresence.SERVICE_STOPPED
        }
    }
}
