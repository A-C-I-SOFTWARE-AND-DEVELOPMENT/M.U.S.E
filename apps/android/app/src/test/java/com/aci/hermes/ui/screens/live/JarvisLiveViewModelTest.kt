package com.aci.hermes.ui.screens.live

import com.aci.hermes.data.emergency.EmergencyStopRepository
import com.aci.hermes.data.emergency.EmergencyStopState
import com.aci.hermes.ui.jarvis.AvatarActivity
import com.aci.hermes.ui.jarvis.IconState
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.launchIn
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File

/**
 * Pins the live-screen view-model's collapse from
 * (service liveness, emergency-stop state, activity hint, reduced-motion)
 * to a rendered avatar spec.
 *
 * The VM does not invent any new safety rules — it only fans the
 * inputs into [AvatarStateMapper]. These tests are guard-rails so a
 * refactor of the source flows can't silently downgrade what the
 * cockpit shows.
 */
class JarvisLiveViewModelTest {

    @get:Rule
    val tmp = TemporaryFolder()

    private lateinit var stopRepo: EmergencyStopRepository
    private lateinit var serviceRunning: MutableStateFlow<Boolean>
    private lateinit var reducedMotion: MutableStateFlow<Boolean>
    private lateinit var vm: JarvisLiveViewModel
    private lateinit var collectionJob: Job

    @Before
    fun setUp() {
        val dir: File = tmp.newFolder()
        stopRepo = EmergencyStopRepository(baseDir = dir, io = Dispatchers.Unconfined)
        serviceRunning = MutableStateFlow(true)
        reducedMotion = MutableStateFlow(false)
        vm = JarvisLiveViewModel(
            emergencyStop = stopRepo,
            serviceRunning = serviceRunning,
            reducedMotion = reducedMotion,
        )
        // The renderSpec StateFlow only emits while subscribed; keep
        // one collector alive for the duration of each test.
        collectionJob = vm.renderSpec.launchIn(CoroutineScope(Dispatchers.Unconfined))
    }

    @After
    fun tearDown() {
        collectionJob.cancel()
    }

    @Test
    fun online_idle_collapses_to_idle_render_spec() = runBlocking {
        serviceRunning.value = true
        stopRepo.setStateForTest(EmergencyStopState.INACTIVE)
        vm.setActivity(AvatarActivity.Idle)
        val spec = vm.renderSpec.first { it.iconState == IconState.IDLE }
        assertEquals(AvatarActivity.Idle, spec.activity)
    }

    @Test
    fun service_down_routes_to_offline() = runBlocking {
        serviceRunning.value = false
        stopRepo.setStateForTest(EmergencyStopState.INACTIVE)
        vm.setActivity(AvatarActivity.Working)
        val spec = vm.renderSpec.first { it.iconState == IconState.OFFLINE }
        assertEquals(AvatarActivity.Blocked, spec.activity)
    }

    @Test
    fun emergency_stop_engaged_routes_to_blocked() = runBlocking {
        serviceRunning.value = true
        stopRepo.setStateForTest(EmergencyStopState.HARD_STOP)
        vm.setActivity(AvatarActivity.Coding)
        val spec = vm.renderSpec.first { it.iconState == IconState.BLOCKED }
        assertEquals(AvatarActivity.Blocked, spec.activity)
    }

    @Test
    fun lockdown_also_blocks() = runBlocking {
        serviceRunning.value = true
        stopRepo.setStateForTest(EmergencyStopState.LOCKDOWN)
        vm.setActivity(AvatarActivity.Testing)
        val spec = vm.renderSpec.first { it.iconState == IconState.BLOCKED }
        assertEquals(AvatarActivity.Blocked, spec.activity)
    }

    @Test
    fun coding_activity_survives_when_inputs_are_idle() = runBlocking {
        serviceRunning.value = true
        stopRepo.setStateForTest(EmergencyStopState.INACTIVE)
        vm.setActivity(AvatarActivity.Coding)
        val spec = vm.renderSpec.first { it.activity == AvatarActivity.Coding }
        assertEquals(IconState.WORKING, spec.iconState)
    }

    @Test
    fun reduced_motion_propagates_through_spec() = runBlocking {
        reducedMotion.value = true
        serviceRunning.value = true
        vm.setActivity(AvatarActivity.Thinking)
        val spec = vm.renderSpec.first { it.reducedMotion }
        assertEquals(0f, spec.effectivePulseAmplitude, 0.0001f)
    }

    @Test
    fun activity_hint_can_be_pushed_repeatedly() = runBlocking {
        vm.setActivity(AvatarActivity.Coding)
        vm.renderSpec.first { it.activity == AvatarActivity.Coding }
        vm.setActivity(AvatarActivity.Testing)
        val spec = vm.renderSpec.first { it.activity == AvatarActivity.Testing }
        assertEquals(IconState.WORKING, spec.iconState)
    }
}

/**
 * Test-only hatch on [EmergencyStopRepository] so we don't need to
 * spin up the full state machine to drive the VM into BLOCKED /
 * LOCKDOWN. The repository's real API is event-driven; this jumps
 * straight to a target state for the purpose of testing what the VM
 * does with it.
 */
private fun EmergencyStopRepository.setStateForTest(state: EmergencyStopState) {
    // Use reflection to set the private _state MutableStateFlow. The
    // repository exposes only an immutable StateFlow; tests need the
    // hatch but the production surface stays unchanged.
    val field = EmergencyStopRepository::class.java.getDeclaredField("_state")
    field.isAccessible = true
    @Suppress("UNCHECKED_CAST")
    val flow = field.get(this) as MutableStateFlow<EmergencyStopState>
    flow.value = state
}
