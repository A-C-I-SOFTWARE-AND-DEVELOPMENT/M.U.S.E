package com.aci.hermes.ui.screens.avatar

import android.app.Application
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import androidx.test.core.app.ApplicationProvider
import com.aci.hermes.data.avatar.AvatarImageStore
import com.aci.hermes.data.avatar.AvatarPixelator
import com.aci.hermes.data.avatar.AvatarRepository
import com.aci.hermes.data.avatar.AvatarSource
import com.aci.hermes.data.avatar.JarvisBuiltin
import com.aci.hermes.data.cockpit.CockpitHttpExecutor
import com.aci.hermes.data.cockpit.CockpitRawResponse
import com.aci.hermes.data.cockpit.CockpitRequest
import com.aci.hermes.data.cockpit.HermesCockpitClient
import com.aci.hermes.testutil.MainDispatcherRule
import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.Job
import kotlinx.coroutines.cancel
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.io.File

@OptIn(ExperimentalCoroutinesApi::class)
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [33])
class AvatarPickerViewModelTest {

    @get:Rule
    val tmp = TemporaryFolder()

    /**
     * One [StandardTestDispatcher] owns the whole test: it is installed as
     * `Dispatchers.Main` (so `viewModelScope` work is virtual), AND it drives the
     * injected DataStore actor + cockpit IO below. With a single scheduler behind
     * all three, `advanceUntilIdle()` deterministically drains the `save()` chain
     * — `viewModelScope.launch { repo.save(...) → store.edit(...) ; _state = Saved }`
     * — instead of racing a real-time poll.
     *
     * Before this change the file used an `UnconfinedTestDispatcher` Main plus a
     * real-time `awaitUntil` poll. But the DataStore write escaped to DataStore's
     * own internal `Dispatchers.IO` actor (no `scope` was passed to the factory),
     * so the `Saved` transition landed on a wall-clock timeline no `TestScheduler`
     * controlled; a contended CI runner occasionally missed the poll deadline and
     * the assertion flaked (#398, #401 — the same test `testutil/Await.kt` already
     * names as a prior offender). Pinning the DataStore scope to this scheduler
     * removes the race at its source, mirroring the deterministic pattern of
     * sibling tests (`JobsViewModelTest`, `DevicePairingViewModelTest`).
     */
    private val dispatcher = StandardTestDispatcher()

    @get:Rule
    val mainDispatcherRule = MainDispatcherRule(dispatcher)

    /**
     * Scope for the injected DataStore actor, pinned to [dispatcher] so its writes
     * run on the test scheduler. Cancelled in [tearDown] so no actor coroutine
     * leaks into the shared Robolectric JVM — the same no-leak discipline
     * [MainDispatcherRule] applies to each registered `viewModelScope`.
     */
    private val dataStoreScope = CoroutineScope(dispatcher + Job())

    @After
    fun tearDown() {
        dataStoreScope.cancel()
    }

    /** A transport that always fails → every cockpit call maps to Unreachable,
     *  so the VM's network-touching init stays benign and offline. */
    private val offlineExecutor = CockpitHttpExecutor { _: CockpitRequest ->
        throw java.io.IOException("offline in test")
        @Suppress("UNREACHABLE_CODE")
        CockpitRawResponse(0, "")
    }

    private fun newVm(): AvatarPickerViewModel {
        val app = ApplicationProvider.getApplicationContext<Application>()
        val imageStore = AvatarImageStore(app)
        val prefsFile = File(tmp.newFolder(), "avatar_prefs_test.preferences_pb")
        val dataStore: DataStore<Preferences> =
            PreferenceDataStoreFactory.create(scope = dataStoreScope) { prefsFile }
        val repo = AvatarRepository(app, imageStore, dataStore)
        val client = HermesCockpitClient(
            endpointProvider = { "" },
            tokenProvider = { null },
            executor = offlineExecutor,
            ioDispatcher = dispatcher,
        )
        return mainDispatcherRule.register(AvatarPickerViewModel(
            application = app,
            pixelator = AvatarPixelator(app, imageStore),
            imageStore = imageStore,
            repo = repo,
            logBuffer = LogBuffer(),
            cockpitClient = client,
        ))
    }


    @Test
    fun `starts idle with no avatar configured`() {
        val vm = newVm()
        // A fresh, isolated DataStore has no saved avatar → stays Idle. The init
        // `repo.current()` coroutine is queued on the (un-advanced) scheduler, so
        // _state holds its initial Idle value; this asserts the start state.
        assertEquals(AvatarPickerState.Idle, vm.state.value)
    }

    @Test
    fun `selecting a built-in stages a preview draft`() {
        val vm = newVm()
        // selectBuiltIn sets _state synchronously (no coroutine), so no advance.
        vm.selectBuiltIn(JarvisBuiltin.GUARDIAN_SHIELD)
        val state = vm.state.value
        assertTrue(state is AvatarPickerState.PreviewReady)
        val ready = state as AvatarPickerState.PreviewReady
        assertEquals(AvatarSource.BUILTIN, ready.draft.source)
        assertEquals(JarvisBuiltin.GUARDIAN_SHIELD, ready.draft.builtin)
    }

    @Test
    fun `saving a previewed built-in persists it`() = runTest {
        val vm = newVm()
        vm.selectBuiltIn(JarvisBuiltin.FAST_WORKER_BOLT)
        vm.save()
        // Drain the save chain (Main-dispatched launch + DataStore actor write,
        // both on `dispatcher`) so the Saved transition is observed deterministically.
        advanceUntilIdle()
        val state = vm.state.value
        assertEquals(AvatarSource.BUILTIN, (state as AvatarPickerState.Saved).profile.source)
    }
}
