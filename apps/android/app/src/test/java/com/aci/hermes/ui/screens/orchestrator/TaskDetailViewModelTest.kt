package com.aci.hermes.ui.screens.orchestrator

import android.app.Application
import androidx.test.core.app.ApplicationProvider
import com.aci.hermes.data.model.TargetTool
import com.aci.hermes.data.orchestrator.HermesTaskRepository
import com.aci.hermes.data.orchestrator.PromptBuilder
import com.aci.hermes.testutil.isolatedSettings
import com.aci.hermes.testutil.awaitUntil
import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@OptIn(ExperimentalCoroutinesApi::class)
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [33])
class TaskDetailViewModelTest {

    private lateinit var tasks: HermesTaskRepository

    private fun newVm(taskId: String?, target: TargetTool? = TargetTool.CODEX): TaskDetailViewModel {
        val app = ApplicationProvider.getApplicationContext<Application>()
        tasks = HermesTaskRepository(app)
        return TaskDetailViewModel(
            application = app,
            tasksRepo = tasks,
            promptBuilder = PromptBuilder(),
            settings = isolatedSettings(app),
            logBuffer = LogBuffer(),
            initialTaskId = taskId,
            initialTarget = target,
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
    fun `a brand new task starts in the new state with a prompt preview`() {
        val vm = newVm(taskId = "new")
        val state = vm.state.value
        assertTrue("a fresh task is marked new", state.isNew)
        assertEquals(TargetTool.CODEX, state.task.targetTool)
        assertTrue("prompt preview should be rendered", state.promptPreview.isNotBlank())
    }

    @Test
    fun `editing a field updates the task and re-renders the preview`() {
        val vm = newVm(taskId = "new")
        vm.setTitle("Tidy the uploader")
        assertEquals("Tidy the uploader", vm.state.value.task.title)
        assertTrue(vm.state.value.promptPreview.contains("Tidy the uploader"))
    }

    @Test
    fun `save persists the task and dismisses`() {
        val vm = newVm(taskId = "new")
        vm.setTitle("Persisted task")
        vm.save()
        awaitUntil(message = "save requests a dismiss") { vm.state.value.dismiss }
        val state = vm.state.value
        assertNotNull("task should be retrievable after save", tasks.byId(state.task.id))
    }
}
