package com.aci.hermes.di

import android.app.Application
import android.content.Context
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import com.aci.hermes.data.gateway.GatewayController
import com.aci.hermes.data.gateway.GatewayMode
import com.aci.hermes.data.model.TargetTool
import com.aci.hermes.data.orchestrator.HermesTaskRepository
import com.aci.hermes.data.orchestrator.PromptBuilder
import com.aci.hermes.data.preferences.GatewayModePref
import com.aci.hermes.data.preferences.SettingsRepository
import com.aci.hermes.ui.screens.diagnostics.DiagnosticsViewModel
import com.aci.hermes.ui.screens.gateway.GatewayViewModel
import com.aci.hermes.ui.screens.orchestrator.OrchestratorViewModel
import com.aci.hermes.ui.screens.orchestrator.TaskDetailViewModel
import com.aci.hermes.ui.screens.settings.SettingsViewModel
import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

/**
 * Hand-rolled DI container. Held by [com.aci.hermes.HermesApplication]
 * for the lifetime of the process. ViewModel factories pull
 * dependencies out of this container.
 *
 * Scope is intentionally tiny — Hermes is a local orchestrator and
 * does not talk to remote services from the app process. The Jarvis
 * Prime [GatewayController] runs in MOCK mode by default; switching to
 * REAL surfaces a clear "transport not implemented" banner instead of
 * silently failing.
 */
class AppContainer(private val application: Application) {

    private val context: Context = application
    private val appScope = CoroutineScope(SupervisorJob() + Dispatchers.Default)

    val logBuffer: LogBuffer = LogBuffer()

    val settingsRepository: SettingsRepository = SettingsRepository(context)

    val taskRepository: HermesTaskRepository = HermesTaskRepository(context)

    val promptBuilder: PromptBuilder = PromptBuilder()

    val gatewayController: GatewayController = GatewayController(logBuffer = logBuffer)

    init {
        appScope.launch {
            val snap = settingsRepository.snapshot()
            gatewayController.switchMode(snap.gatewayMode.toGatewayMode())
        }
    }

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
        SettingsViewModel(settingsRepository, taskRepository, gatewayController, logBuffer)
    }

    fun diagnosticsVmFactory(): ViewModelProvider.Factory = factory {
        DiagnosticsViewModel(logBuffer)
    }

    fun gatewayVmFactory(): ViewModelProvider.Factory = factory {
        GatewayViewModel(gatewayController, logBuffer)
    }

    private inline fun <reified VM : ViewModel> factory(crossinline build: () -> VM): ViewModelProvider.Factory =
        object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T = build() as T
        }
}

internal fun GatewayModePref.toGatewayMode(): GatewayMode = when (this) {
    GatewayModePref.MOCK -> GatewayMode.MOCK
    GatewayModePref.REAL -> GatewayMode.REAL
}
