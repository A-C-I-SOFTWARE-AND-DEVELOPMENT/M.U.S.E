package com.aci.hermes.ui.screens.jarvis_live

import android.app.Application
import android.app.ActivityManager
import android.content.Context
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.model.HermesTask
import com.aci.hermes.data.model.TaskStatus
import com.aci.hermes.data.orchestrator.HermesTaskRepository
import com.aci.hermes.service.HermesService
import com.aci.hermes.ui.jarvis.IconState
import com.aci.hermes.ui.jarvis.IconStateMapper
import com.aci.hermes.ui.jarvis.JarvisChatStreamState
import com.aci.hermes.ui.jarvis.JarvisLiveInputs
import com.aci.hermes.ui.jarvis.JarvisLiveStatus
import com.aci.hermes.ui.jarvis.JarvisLiveStatusProjector
import com.aci.hermes.ui.jarvis.JarvisWorkerPhase
import com.aci.hermes.ui.jarvis.OrchestratorIconStateMapping
import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/**
 * Live screen UI state. The [status] is recomputed from [snapshot]
 * through [JarvisLiveStatusProjector] inside the screen rather than
 * cached here — keeps the source of truth in one place.
 */
data class JarvisLiveUiState(
    val serviceRunning: Boolean = false,
    val tasks: List<HermesTask> = emptyList(),
    val workerPhase: JarvisWorkerPhase = JarvisWorkerPhase.NONE,
    val chatStream: JarvisChatStreamState = JarvisChatStreamState.IDLE,
    val approvalQueueCount: Int = 0,
    val emergencyStopActive: Boolean = false,
    val activeTaskTitle: String? = null,
    val activeTaskStepLabel: String? = null,
    val activeTaskStepIndex: Int? = null,
    val activeTaskStepTotal: Int? = null,
    val draft: String = "",
    val snackbar: String? = null,
)

/**
 * View model for [JarvisLiveScreen]. Re-uses
 * [OrchestratorIconStateMapping] for the icon-state derivation so the
 * live screen always agrees with the orchestrator on what Jarvis is
 * doing. Producers for worker phase, chat stream, approval count, and
 * emergency stop are scaffolded as [setWorkerPhase] / etc. — the
 * future chat-screen and worker branches plug into these entry points.
 */
class JarvisLiveViewModel(
    application: Application,
    private val tasksRepo: HermesTaskRepository,
    private val logBuffer: LogBuffer,
) : AndroidViewModel(application) {

    private val _state = MutableStateFlow(JarvisLiveUiState())
    val state: StateFlow<JarvisLiveUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            tasksRepo.tasks.collect { list ->
                _state.update { current ->
                    current.copy(
                        tasks = list,
                        activeTaskTitle = pickActiveTaskTitle(list)
                            ?: current.activeTaskTitle,
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

    fun setWorkerPhase(phase: JarvisWorkerPhase) {
        _state.update { it.copy(workerPhase = phase) }
        logBuffer.info("JarvisLive", "worker phase → $phase")
    }

    fun setChatStream(stream: JarvisChatStreamState) {
        _state.update { it.copy(chatStream = stream) }
    }

    fun setApprovalQueueCount(count: Int) {
        _state.update { it.copy(approvalQueueCount = count.coerceAtLeast(0)) }
    }

    fun setEmergencyStop(active: Boolean) {
        _state.update { it.copy(emergencyStopActive = active) }
        logBuffer.info("JarvisLive", "emergency stop → $active")
    }

    fun setProgress(
        stepLabel: String?,
        stepIndex: Int?,
        stepTotal: Int?,
    ) {
        _state.update {
            it.copy(
                activeTaskStepLabel = stepLabel,
                activeTaskStepIndex = stepIndex,
                activeTaskStepTotal = stepTotal,
            )
        }
    }

    fun updateDraft(value: String) {
        _state.update { it.copy(draft = value) }
    }

    fun sendDraft() {
        val text = _state.value.draft.trim()
        if (text.isEmpty()) return
        logBuffer.info("JarvisLive", "ask jarvis → '$text' (no gateway wired yet)")
        _state.update {
            it.copy(
                draft = "",
                snackbar = "Sent to Jarvis (preview).",
            )
        }
    }

    fun consumeSnackbar() {
        _state.update { it.copy(snackbar = null) }
    }

    fun acknowledgeApproval() {
        logBuffer.info("JarvisLive", "approval acknowledged (preview)")
        _state.update { it.copy(snackbar = "Approval queue opens here in a later wave.") }
    }

    fun triggerEmergencyStop() {
        logBuffer.info("JarvisLive", "emergency stop pressed (preview)")
        _state.update {
            it.copy(
                snackbar = "Emergency stop confirmation lands here in a later wave.",
            )
        }
    }

    /**
     * Project current state through the pure projector. Called by the
     * screen; kept here so the screen does not import the projector
     * directly and so this VM can be tested in isolation.
     */
    fun projectStatus(reducedMotion: Boolean): JarvisLiveStatus {
        val snapshot = _state.value
        val iconState: IconState = IconStateMapper.map(
            OrchestratorIconStateMapping.inputsFor(
                serviceRunning = snapshot.serviceRunning,
                tasks = snapshot.tasks,
                pendingApproval = snapshot.approvalQueueCount > 0,
            )
        )
        return JarvisLiveStatusProjector.project(
            JarvisLiveInputs(
                iconState = iconState,
                activeTaskTitle = snapshot.activeTaskTitle,
                activeTaskStepLabel = snapshot.activeTaskStepLabel,
                activeTaskStepIndex = snapshot.activeTaskStepIndex,
                activeTaskStepTotal = snapshot.activeTaskStepTotal,
                workerPhase = snapshot.workerPhase,
                chatStream = snapshot.chatStream,
                approvalQueueCount = snapshot.approvalQueueCount,
                emergencyStopActive = snapshot.emergencyStopActive,
                gatewayOnline = snapshot.serviceRunning,
                reducedMotion = reducedMotion,
            )
        )
    }

    private fun pickActiveTaskTitle(tasks: List<HermesTask>): String? {
        // Prefer in-flight tasks first, then most-recently-updated.
        val activeStatuses = setOf(
            TaskStatus.HANDED_TO_CODEX,
            TaskStatus.HANDED_TO_CLAUDE,
            TaskStatus.IN_REVIEW,
        )
        val active = tasks.filter { it.status in activeStatuses }
            .maxByOrNull { it.updatedAt }
        if (active != null) return active.title.ifBlank { null }
        return tasks.maxByOrNull { it.updatedAt }?.title?.ifBlank { null }
    }

    @Suppress("DEPRECATION")
    private fun isServiceRunning(context: Context, cls: Class<*>): Boolean {
        val am = context.getSystemService(Context.ACTIVITY_SERVICE) as? ActivityManager
            ?: return false
        return am.getRunningServices(Integer.MAX_VALUE)
            .any { it.service.className == cls.name }
    }
}
