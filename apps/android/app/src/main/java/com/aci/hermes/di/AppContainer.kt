package com.aci.hermes.di

import android.app.Application
import android.content.Context
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import com.aci.hermes.data.model.TargetTool
import com.aci.hermes.data.orchestrator.HermesTaskRepository
import com.aci.hermes.data.orchestrator.PromptBuilder
import com.aci.hermes.data.preferences.SettingsRepository
import com.aci.hermes.safety.EmergencyStop
import com.aci.hermes.safety.PermissionKernel
import com.aci.hermes.ui.screens.diagnostics.DiagnosticsViewModel
import com.aci.hermes.ui.screens.orchestrator.OrchestratorViewModel
import com.aci.hermes.ui.screens.orchestrator.TaskDetailViewModel
import com.aci.hermes.ui.screens.settings.SettingsViewModel
import com.aci.hermes.util.LogBuffer
import java.util.concurrent.atomic.AtomicReference

/**
 * Process-scoped DI container for Jarvis Prime. Owned by
 * [com.aci.hermes.HermesApplication]. ViewModel factories pull
 * dependencies from here so screens never instantiate subsystems
 * directly.
 *
 * The Activity binds its system-prompt launcher into the container so
 * the [PermissionKernel] can hand off to the OS dialog from anywhere
 * in the app without holding an Activity reference.
 */
class AppContainer(private val application: Application) {

    private val context: Context = application

    val logBuffer: LogBuffer = LogBuffer()

    val settingsRepository: SettingsRepository = SettingsRepository(context)

    val taskRepository: HermesTaskRepository = HermesTaskRepository(context)

    val promptBuilder: PromptBuilder = PromptBuilder()

    val permissionKernel: PermissionKernel = PermissionKernel()

    val emergencyStop: EmergencyStop = EmergencyStop()

    private val activityLauncher = AtomicReference<PermissionKernel.SystemPromptLauncher?>(null)

    fun bindActivityPromptLauncher(launcher: PermissionKernel.SystemPromptLauncher) {
        activityLauncher.set(launcher)
    }

    fun unbindActivityPromptLauncher(launcher: PermissionKernel.SystemPromptLauncher) {
        activityLauncher.compareAndSet(launcher, null)
    }

    fun systemPromptLauncher(): PermissionKernel.SystemPromptLauncher? = activityLauncher.get()

    fun orchestratorVmFactory(): ViewModelProvider.Factory = factory {
        OrchestratorViewModel(
            application = application,
            settings = settingsRepository,
            tasksRepo = taskRepository,
            promptBuilder = promptBuilder,
            logBuffer = logBuffer,
        )
    }

    fun taskDetailVmFactory(taskId: String?, initialTarget: TargetTool?): ViewModelProvider.Factory = factory {
        TaskDetailViewModel(
            application = application,
            tasksRepo = taskRepository,
            promptBuilder = promptBuilder,
            settings = settingsRepository,
            logBuffer = logBuffer,
            initialTaskId = taskId,
            initialTarget = initialTarget,
        )
    }

    fun settingsVmFactory(): ViewModelProvider.Factory = factory {
        SettingsViewModel(settingsRepository, taskRepository, logBuffer)
    }

    fun diagnosticsVmFactory(): ViewModelProvider.Factory = factory {
        DiagnosticsViewModel(logBuffer)
    }

    private inline fun <reified VM : ViewModel> factory(crossinline build: () -> VM): ViewModelProvider.Factory =
        object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T = build() as T
        }
}
