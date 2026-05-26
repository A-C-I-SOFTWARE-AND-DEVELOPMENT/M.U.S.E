package com.aci.hermes.ui.screens.orchestrator

import android.app.Application
import android.app.ActivityManager
import android.content.Context
import android.content.Intent
import androidx.core.content.ContextCompat
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.emergency.EmergencyStopController
import com.aci.hermes.data.emergency.EmergencyStopState
import com.aci.hermes.data.emergency.GuardedAction
import com.aci.hermes.data.model.AiToolProfile
import com.aci.hermes.data.model.DefaultToolProfiles
import com.aci.hermes.data.model.HermesTask
import com.aci.hermes.data.orchestrator.HandoffLauncher
import com.aci.hermes.data.orchestrator.HermesTaskRepository
import com.aci.hermes.data.orchestrator.PromptBuilder
import com.aci.hermes.data.preferences.SettingsRepository
import com.aci.hermes.service.HermesService
import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class OrchestratorUiState(
    val serviceRunning: Boolean = false,
    val mode: String = HermesService.DEFAULT_MODE,
    val tools: List<AiToolProfile> = DefaultToolProfiles.all,
    val tasks: List<HermesTask> = emptyList(),
    val allowExternalAppOpening: Boolean = false,
    val clipboardHandoffEnabled: Boolean = true,
    val showSafetyWarnings: Boolean = true,
    val emergencyStop: EmergencyStopState = EmergencyStopState.INACTIVE,
    val snackbar: String? = null,
)

class OrchestratorViewModel(
    application: Application,
    private val settings: SettingsRepository,
    private val tasksRepo: HermesTaskRepository,
    private val promptBuilder: PromptBuilder,
    private val logBuffer: LogBuffer,
    private val emergencyStop: EmergencyStopController,
) : AndroidViewModel(application) {

    private val _state = MutableStateFlow(OrchestratorUiState())
    val state: StateFlow<OrchestratorUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            tasksRepo.tasks.collect { list ->
                _state.update { it.copy(tasks = list) }
            }
        }
        viewModelScope.launch {
            combine(
                settings.allowExternalAppOpening,
                settings.clipboardHandoffEnabled,
                settings.showSafetyWarnings,
            ) { a, b, c -> Triple(a, b, c) }.collect { (allowExternal, clipboard, warnings) ->
                _state.update {
                    it.copy(
                        allowExternalAppOpening = allowExternal,
                        clipboardHandoffEnabled = clipboard,
                        showSafetyWarnings = warnings,
                    )
                }
            }
        }
        viewModelScope.launch {
            emergencyStop.state.collect { es ->
                _state.update { it.copy(emergencyStop = es) }
            }
        }
        refreshServiceStatus()
    }

    fun refreshServiceStatus() {
        val ctx = getApplication<Application>()
        val running = isServiceRunning(ctx, HermesService::class.java)
        _state.update { it.copy(serviceRunning = running) }
    }

    fun startService() {
        val ctx = getApplication<Application>()
        val intent = Intent(ctx, HermesService::class.java).apply {
            putExtra(HermesService.EXTRA_LAUNCH_SOURCE, "dashboard_start")
            putExtra(HermesService.EXTRA_MODE, HermesService.DEFAULT_MODE)
        }
        ContextCompat.startForegroundService(ctx, intent)
        logBuffer.info(HermesService.TAG, "Service start requested from dashboard")
        refreshServiceStatus()
    }

    fun stopService() {
        val ctx = getApplication<Application>()
        ctx.stopService(Intent(ctx, HermesService::class.java))
        logBuffer.info(HermesService.TAG, "Service stop requested from dashboard")
        refreshServiceStatus()
    }

    fun copyPromptForTask(taskId: String) {
        val task = tasksRepo.byId(taskId) ?: return
        copyPromptForTask(task)
    }

    fun copyPromptForTask(task: HermesTask) {
        viewModelScope.launch {
            if (!emergencyStop.guard(GuardedAction.SEND, source = "Orchestrator.copyPrompt")) {
                _state.update {
                    it.copy(snackbar = "Blocked by emergency stop — open Jarvis Control to resume.")
                }
                return@launch
            }
            val profile = DefaultToolProfiles.byTargetTool(task.targetTool)
            val prompt = promptBuilder.build(task, profile)
            val ok = HandoffLauncher.copyPrompt(
                getApplication(),
                label = "Hermes prompt",
                text = prompt,
            )
            if (ok) {
                _state.update { it.copy(snackbar = "Prompt copied to clipboard") }
                logBuffer.info("Orchestrator", "Copied prompt for task ${task.id}")
            } else {
                _state.update { it.copy(snackbar = "Failed to access clipboard") }
            }
        }
    }

    fun openToolFor(profile: AiToolProfile) {
        viewModelScope.launch {
            if (!emergencyStop.guard(GuardedAction.SEND, source = "Orchestrator.openTool")) {
                _state.update {
                    it.copy(snackbar = "Blocked by emergency stop — open Jarvis Control to resume.")
                }
                return@launch
            }
            val result = HandoffLauncher.openOfficialTool(
                context = getApplication(),
                profile = profile,
                allowExternal = _state.value.allowExternalAppOpening,
            )
            val msg = when (result) {
                is HandoffLauncher.LaunchResult.Opened -> "Opened ${profile.displayName} (${result.via})"
                is HandoffLauncher.LaunchResult.ManualOnly -> result.message
                HandoffLauncher.LaunchResult.Blocked ->
                    "External app opening is disabled in Settings → Orchestrator preferences."
            }
            _state.update { it.copy(snackbar = msg) }
        }
    }

    fun guardNewTask(): Boolean {
        val blocked = emergencyStop.isBlocked(GuardedAction.START_TASK)
        if (blocked) {
            _state.update {
                it.copy(snackbar = "Blocked by emergency stop — new tasks paused.")
            }
        }
        return !blocked
    }

    fun consumeSnackbar() {
        _state.update { it.copy(snackbar = null) }
    }

    @Suppress("DEPRECATION")
    private fun isServiceRunning(context: Context, cls: Class<*>): Boolean {
        // ActivityManager.getRunningServices is deprecated for cross-app
        // queries but still works for the caller's own services, which
        // is what we need here.
        val am = context.getSystemService(Context.ACTIVITY_SERVICE) as? ActivityManager ?: return false
        return am.getRunningServices(Integer.MAX_VALUE)
            .any { it.service.className == cls.name }
    }
}
