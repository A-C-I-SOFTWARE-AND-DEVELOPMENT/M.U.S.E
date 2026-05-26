package com.aci.hermes.di

import android.app.Application
import android.content.Context
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import com.aci.hermes.data.jarvis.AndroidJarvisClipboard
import com.aci.hermes.data.jarvis.JarvisChatGateway
import com.aci.hermes.data.jarvis.JarvisClipboard
import com.aci.hermes.data.jarvis.JarvisTaskSink
import com.aci.hermes.data.jarvis.MockJarvisChatGateway
import com.aci.hermes.data.jarvis.RepositoryTaskSink
import com.aci.hermes.data.model.TargetTool
import com.aci.hermes.data.orchestrator.HermesTaskRepository
import com.aci.hermes.data.orchestrator.PromptBuilder
import com.aci.hermes.data.preferences.SettingsRepository
import com.aci.hermes.ui.screens.diagnostics.DiagnosticsViewModel
import com.aci.hermes.ui.screens.jarvis.JarvisChatViewModel
import com.aci.hermes.ui.screens.orchestrator.OrchestratorViewModel
import com.aci.hermes.ui.screens.orchestrator.TaskDetailViewModel
import com.aci.hermes.ui.screens.settings.SettingsViewModel
import com.aci.hermes.util.LogBuffer

/**
 * Hand-rolled DI container. Held by [com.aci.hermes.HermesApplication]
 * for the lifetime of the process. ViewModel factories pull
 * dependencies out of this container.
 *
 * Scope is intentionally tiny — Hermes is a local orchestrator and
 * does not talk to remote services from the app process.
 */
class AppContainer(private val application: Application) {

    private val context: Context = application

    val logBuffer: LogBuffer = LogBuffer()

    val settingsRepository: SettingsRepository = SettingsRepository(context)

    val taskRepository: HermesTaskRepository = HermesTaskRepository(context)

    val promptBuilder: PromptBuilder = PromptBuilder()

    /**
     * Jarvis Prime chat gateway. Mock implementation today; the live
     * cockpit-backed gateway plugs in here when it lands without
     * touching the chat screen.
     */
    val jarvisChatGateway: JarvisChatGateway = MockJarvisChatGateway()

    val jarvisClipboard: JarvisClipboard = AndroidJarvisClipboard(context)

    val jarvisTaskSink: JarvisTaskSink = RepositoryTaskSink(taskRepository)

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

    fun jarvisChatVmFactory(): ViewModelProvider.Factory = factory {
        JarvisChatViewModel(
            gateway = jarvisChatGateway,
            taskSink = jarvisTaskSink,
            logBuffer = logBuffer,
            clipboard = jarvisClipboard,
        )
    }

    private inline fun <reified VM : ViewModel> factory(crossinline build: () -> VM): ViewModelProvider.Factory =
        object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T = build() as T
        }
}
