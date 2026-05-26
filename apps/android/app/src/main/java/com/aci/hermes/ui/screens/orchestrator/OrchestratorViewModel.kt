package com.aci.hermes.ui.screens.orchestrator

import android.app.Application
import android.app.ActivityManager
import android.content.Context
import android.content.Intent
import androidx.core.content.ContextCompat
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.model.AiToolProfile
import com.aci.hermes.data.model.DefaultToolProfiles
import com.aci.hermes.data.model.HermesTask
import com.aci.hermes.data.orchestrator.HandoffLauncher
import com.aci.hermes.data.orchestrator.HermesTaskRepository
import com.aci.hermes.data.orchestrator.PromptBuilder
import com.aci.hermes.data.preferences.SettingsRepository
import com.aci.hermes.service.HermesService
import com.aci.hermes.ui.jarvis.IconState
import com.aci.hermes.ui.jarvis.IconStateMapper
import com.aci.hermes.ui.jarvis.OrchestratorIconStateMapping
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
    val snackbar: String? = null,
) {
    /**
     * Derived Jarvis Prime icon state. The mapper is pure and cheap,
     * so we recompute on every snapshot rather than storing the value.
     */
    val jarvisIconState: IconState
        get() = IconStateMapper.map(
            OrchestratorIconStateMapping.inputsFor(
                serviceRunning = serviceRunning,
                tasks = tasks,
            )
        )
}

class OrchestratorViewModel(
    application: Application,
    private val settings: SettingsRepository,
    private val tasksRepo: HermesTaskRepository,
    private val promptBuilder: PromptBuilder,
    private val logBuffer: LogBuffer,
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

    fun openToolFor(profile: AiToolProfile) {
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

    fun consumeSnackbar() {
        _state.update { it.copy(snackbar = null) }
    }

    // --- Jarvis Prime icon handlers --------------------------------
    //
    // The icon's gesture vocabulary is wired here so the ViewModel
    // controls navigation/messaging surfaces. Chat and Voice Capture
    // screens land in a later wave — until they exist, taps surface a
    // snackbar so the gesture path is still observable in QA.

    fun onJarvisTap() {
        val msg = "Chat opens here in a later wave"
        logBuffer.info("Jarvis", "tap → chat (placeholder)")
        _state.update { it.copy(snackbar = msg) }
    }

    fun onJarvisHold() {
        val msg = "Voice capture starts here in a later wave"
        logBuffer.info("Jarvis", "hold → voice capture (placeholder)")
        _state.update { it.copy(snackbar = msg) }
    }

    fun onJarvisLongPress() {
        val msg = "Emergency stop confirmation lands here in a later wave"
        logBuffer.info("Jarvis", "long press → emergency stop (placeholder)")
        _state.update { it.copy(snackbar = msg) }
    }

    fun onJarvisDoubleTap() {
        val label = _state.value.jarvisIconState.toReadableLabel()
        logBuffer.info("Jarvis", "double tap → status: $label")
        _state.update { it.copy(snackbar = "Jarvis status: $label") }
    }

    fun onJarvisSwipeUp() {
        logBuffer.info("Jarvis", "swipe up → tasks (already showing)")
        _state.update { it.copy(snackbar = "Tasks") }
    }

    private fun IconState.toReadableLabel(): String =
        name.lowercase().replace('_', ' ')

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
