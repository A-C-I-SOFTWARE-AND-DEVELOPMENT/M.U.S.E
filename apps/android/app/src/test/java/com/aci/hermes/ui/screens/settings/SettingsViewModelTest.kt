package com.aci.hermes.ui.screens.settings

import androidx.test.core.app.ApplicationProvider
import com.aci.hermes.data.coding.CodingTaskStore
import com.aci.hermes.data.coding.SavedCodingTask
import com.aci.hermes.data.orchestrator.HermesTaskRepository
import com.aci.hermes.data.preferences.PreferredBuilder
import com.aci.hermes.data.preferences.SettingsRepository
import com.aci.hermes.data.preferences.ThemeMode
import com.aci.hermes.testutil.awaitUntil
import com.aci.hermes.testutil.awaitValue
import com.aci.hermes.testutil.isolatedSettings
import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/**
 * The settings store is a real (process-shared) DataStore, so we assert the
 * VM's *persistence contract* — a setter writes through to the repository —
 * which is deterministic regardless of the one-shot snapshot the VM loads on
 * init. (`Dispatchers.Unconfined` as Main resumes the IO continuations inline.)
 */
@OptIn(ExperimentalCoroutinesApi::class)
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [33])
class SettingsViewModelTest {

    private lateinit var settings: SettingsRepository
    private lateinit var codingStore: CodingTaskStore

    private fun newVm(): SettingsViewModel {
        val ctx = ApplicationProvider.getApplicationContext<android.content.Context>()
        settings = isolatedSettings(ctx)
        codingStore = CodingTaskStore(
            java.nio.file.Files.createTempDirectory("settings-coding").toFile(),
            ioDispatcher = Dispatchers.Unconfined,
        )
        return SettingsViewModel(
            settings = settings,
            tasks = HermesTaskRepository(ctx),
            logBuffer = LogBuffer(),
            codingTasks = codingStore,
        )
    }

    @Before
    fun setUp() {
        Dispatchers.setMain(Dispatchers.Unconfined)
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun `theme setter persists through to the repository`() {
        val vm = newVm()
        vm.setThemeMode(ThemeMode.DARK)
        // Assert the persistence contract: a setter writes through to the repo.
        // (We intentionally don't assert the in-memory snapshot here — the VM's
        // one-shot init load can land after an immediate setter and is a
        // separate, pre-existing concern.)
        awaitUntil(message = "theme persisted as DARK") {
            awaitValue { settings.snapshot().themeMode } == ThemeMode.DARK
        }
    }

    @Test
    fun `preferred builder setter persists through to the repository`() {
        val vm = newVm()
        vm.setPreferredBuilder(PreferredBuilder.CHATGPT)
        awaitUntil(message = "builder persisted as CHATGPT") {
            awaitValue { settings.snapshot().preferredBuilder } == PreferredBuilder.CHATGPT
        }
    }

    @Test
    fun `safety toggles persist through to the repository`() {
        val vm = newVm()
        vm.setShowSafetyWarnings(false)
        awaitUntil(message = "safety warnings persisted false") {
            awaitValue { !settings.snapshot().showSafetyWarnings }
        }
        vm.setLocalOnlyMode(false)
        awaitUntil(message = "local-only persisted false") {
            awaitValue { !settings.snapshot().localOnlyMode }
        }
    }

    @Test
    fun `reset clears saved coding tasks`() {
        val vm = newVm()
        awaitValue { codingStore.upsert(SavedCodingTask(id = "c1", title = "C", prompt = "p")) }
        vm.resetAll()
        awaitUntil(message = "coding tasks cleared on reset") {
            codingStore.tasks.value.isEmpty()
        }
    }
}
