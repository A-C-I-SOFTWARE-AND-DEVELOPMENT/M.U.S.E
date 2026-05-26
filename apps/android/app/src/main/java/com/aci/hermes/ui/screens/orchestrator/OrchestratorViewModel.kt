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
import com.aci.hermes.data.model.TaskSection
import com.aci.hermes.data.model.TaskStatus
import com.aci.hermes.data.model.WorkerPhase
import com.aci.hermes.data.model.lane
import com.aci.hermes.data.model.section
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
    val sections: Map<TaskSection, List<HermesTask>> = emptyMap(),
    val workerLanes: List<WorkerLaneState> = WorkerLaneState.empty(),
    val emergencyStopActive: Boolean = false,
    val allowExternalAppOpening: Boolean = false,
    val clipboardHandoffEnabled: Boolean = true,
    val showSafetyWarnings: Boolean = true,
    val snackbar: String? = null,
)

/** One row on the Worker Lanes dashboard card. */
data class WorkerLaneState(
    val phase: WorkerPhase,
    val activeTasks: List<HermesTask>,
) {
    val isBusy: Boolean get() = activeTasks.isNotEmpty()

    companion object {
        fun empty(): List<WorkerLaneState> = WorkerPhase.entries.map { WorkerLaneState(it, emptyList()) }
    }
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
                _state.update {
                    it.copy(
                        tasks = list,
                        sections = sectionTasks(list),
                        workerLanes = laneStates(list),
                        emergencyStopActive = list.any { t -> t.emergencyStopActive },
                    )
                }
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

    /** Disarms the emergency-stop banner across every persisted task. */
    fun clearEmergencyStop() {
        viewModelScope.launch {
            tasksRepo.tasks.value
                .filter { it.emergencyStopActive }
                .forEach { tasksRepo.upsert(it.copy(emergencyStopActive = false)) }
            _state.update { it.copy(snackbar = "Emergency stop cleared.") }
        }
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

    companion object {
        /** Groups [tasks] into the Tasks-screen sections. Pure / test-friendly. */
        fun sectionTasks(tasks: List<HermesTask>): Map<TaskSection, List<HermesTask>> {
            val grouped = tasks.groupBy { it.status.section() }
            // Preserve display order (Active → Waiting → Blocked → Failed → Complete).
            return TaskSection.entries.associateWith { grouped[it].orEmpty() }
        }

        /** Computes the per-lane busy state. Pure / test-friendly. */
        fun laneStates(tasks: List<HermesTask>): List<WorkerLaneState> {
            // A task belongs to the lane its current TaskStatus maps to, OR
            // — if its status doesn't pin it to one — its persisted workerPhase.
            val byLane: Map<WorkerPhase, List<HermesTask>> = tasks
                .filter { it.status != TaskStatus.COMPLETE && !it.emergencyStopActive }
                .groupBy { task -> task.status.lane() ?: task.workerPhase }
            return WorkerPhase.entries.map { phase ->
                WorkerLaneState(phase = phase, activeTasks = byLane[phase].orEmpty())
            }
        }
    }
}
