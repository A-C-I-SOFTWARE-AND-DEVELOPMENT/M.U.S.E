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
import com.aci.hermes.testutil.awaitUntil
import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
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

    @get:Rule
    val mainDispatcherRule = MainDispatcherRule()

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
        val dataStore: DataStore<Preferences> = PreferenceDataStoreFactory.create { prefsFile }
        val repo = AvatarRepository(app, imageStore, dataStore)
        val client = HermesCockpitClient(
            endpointProvider = { "" },
            tokenProvider = { null },
            executor = offlineExecutor,
            ioDispatcher = Dispatchers.Unconfined,
        )
        return AvatarPickerViewModel(
            application = app,
            pixelator = AvatarPixelator(app, imageStore),
            imageStore = imageStore,
            repo = repo,
            logBuffer = LogBuffer(),
            cockpitClient = client,
        )
    }


    @Test
    fun `starts idle with no avatar configured`() {
        val vm = newVm()
        // A fresh, isolated DataStore has no saved avatar → stays Idle.
        assertEquals(AvatarPickerState.Idle, vm.state.value)
    }

    @Test
    fun `selecting a built-in stages a preview draft`() {
        val vm = newVm()
        vm.selectBuiltIn(JarvisBuiltin.GUARDIAN_SHIELD)
        val state = vm.state.value
        assertTrue(state is AvatarPickerState.PreviewReady)
        val ready = state as AvatarPickerState.PreviewReady
        assertEquals(AvatarSource.BUILTIN, ready.draft.source)
        assertEquals(JarvisBuiltin.GUARDIAN_SHIELD, ready.draft.builtin)
    }

    @Test
    fun `saving a previewed built-in persists it`() {
        val vm = newVm()
        vm.selectBuiltIn(JarvisBuiltin.FAST_WORKER_BOLT)
        vm.save()
        awaitUntil(message = "save lands in the Saved state") {
            vm.state.value is AvatarPickerState.Saved
        }
        val state = vm.state.value
        assertEquals(AvatarSource.BUILTIN, (state as AvatarPickerState.Saved).profile.source)
    }
}
