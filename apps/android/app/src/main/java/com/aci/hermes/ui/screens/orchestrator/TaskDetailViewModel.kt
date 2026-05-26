package com.aci.hermes.ui.screens.orchestrator

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.model.AiToolProfile
import com.aci.hermes.data.model.DefaultToolProfiles
import com.aci.hermes.data.model.HermesTask
import com.aci.hermes.data.model.TargetTool
import com.aci.hermes.data.model.TaskStatus
import com.aci.hermes.data.model.TaskType
import com.aci.hermes.data.orchestrator.HandoffLauncher
import com.aci.hermes.data.orchestrator.HermesTaskRepository
import com.aci.hermes.data.orchestrator.PromptBuilder
import com.aci.hermes.data.preferences.SettingsRepository
import com.aci.hermes.util.LogBuffer
import com.aci.hermes.voice.VoicePendingDraft
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class TaskDetailUiState(
    val task: HermesTask = HermesTask(),
    val promptPreview: String = "",
    val isNew: Boolean = true,
    val saving: Boolean = false,
    val snackbar: String? = null,
    val dismiss: Boolean = false,
    val allowExternalAppOpening: Boolean = false,
)

class TaskDetailViewModel(
    application: Application,
    private val tasksRepo: HermesTaskRepository,
    private val promptBuilder: PromptBuilder,
    private val settings: SettingsRepository,
    private val logBuffer: LogBuffer,
    initialTaskId: String?,
    initialTarget: TargetTool?,
    voicePendingDraft: VoicePendingDraft? = null,
) : AndroidViewModel(application) {

    private val _state = MutableStateFlow(TaskDetailUiState())
    val state: StateFlow<TaskDetailUiState> = _state.asStateFlow()

    init {
        val existing = initialTaskId?.takeIf { it.isNotBlank() && it != "new" }
            ?.let { tasksRepo.byId(it) }
        val pendingVoiceDraft = if (existing == null) voicePendingDraft?.consume() else null
        val voicePrefill = pendingVoiceDraft?.let { draft ->
            val approvalNote = if (draft.requiresApproval) {
                "\n\n⚠ Voice capture flagged this as approval-required" +
                    (draft.reason?.let { " — $it" } ?: "") +
                    ". Do not hand off until you have reviewed."
            } else {
                ""
            }
            draft.transcript.trim() + approvalNote
        }
        val base = existing ?: HermesTask(
            targetTool = initialTarget ?: TargetTool.CODEX,
            description = voicePrefill.orEmpty(),
            title = pendingVoiceDraft?.let {
                val first = it.transcript.trim().split(Regex("[.!?\\n]"))
                    .firstOrNull { line -> line.isNotBlank() }
                    ?.take(80) ?: ""
                if (it.requiresApproval) "[Approval needed] $first".trim() else first
            }.orEmpty(),
        )
        _state.value = TaskDetailUiState(
            task = base,
            promptPreview = promptBuilder.build(base, profileFor(base.targetTool)),
            isNew = existing == null,
        )
        viewModelScope.launch {
            settings.allowExternalAppOpening.collect { allowed ->
                _state.update { it.copy(allowExternalAppOpening = allowed) }
            }
        }
    }

    fun setTitle(value: String) = updateTask { it.copy(title = value) }
    fun setDescription(value: String) = updateTask { it.copy(description = value) }
    fun setWorkspacePath(value: String) = updateTask { it.copy(workspacePath = value.ifBlank { null }) }
    fun setNextAction(value: String) = updateTask { it.copy(nextAction = value.ifBlank { null }) }
    fun setReviewNotes(value: String) = updateTask { it.copy(reviewNotes = value.ifBlank { null }) }
    fun setResultNotes(value: String) = updateTask { it.copy(resultNotes = value.ifBlank { null }) }
    fun setTaskType(value: TaskType) = updateTask { it.copy(taskType = value) }
    fun setStatus(value: TaskStatus) = updateTask { it.copy(status = value) }
    fun setTargetTool(value: TargetTool) = updateTask { it.copy(targetTool = value) }

    fun save() {
        val current = _state.value.task
        viewModelScope.launch {
            _state.update { it.copy(saving = true) }
            tasksRepo.upsert(current)
            logBuffer.info("Orchestrator", "Saved task ${current.id}")
            _state.update { it.copy(saving = false, isNew = false, snackbar = "Task saved", dismiss = true) }
        }
    }

    fun delete() {
        val id = _state.value.task.id
        viewModelScope.launch {
            tasksRepo.delete(id)
            logBuffer.info("Orchestrator", "Deleted task $id")
            _state.update { it.copy(dismiss = true) }
        }
    }

    fun copyPrompt() {
        val ok = HandoffLauncher.copyPrompt(
            getApplication(),
            label = "Hermes prompt",
            text = _state.value.promptPreview,
        )
        _state.update { it.copy(snackbar = if (ok) "Prompt copied to clipboard" else "Failed to access clipboard") }
    }

    fun markHandedOff() {
        val task = _state.value.task
        val newStatus = when (task.targetTool) {
            TargetTool.CODEX, TargetTool.CHATGPT -> TaskStatus.HANDED_TO_CODEX
            TargetTool.CLAUDE_CODE, TargetTool.CLAUDE -> TaskStatus.HANDED_TO_CLAUDE
            TargetTool.MANUAL -> TaskStatus.READY_FOR_HANDOFF
        }
        setStatus(newStatus)
        viewModelScope.launch {
            tasksRepo.upsert(_state.value.task)
            _state.update { it.copy(snackbar = "Marked as handed off") }
        }
    }

    fun openTool() {
        val task = _state.value.task
        val profile = profileFor(task.targetTool)
        if (profile == null) {
            _state.update { it.copy(snackbar = "Manual target — no tool to open.") }
            return
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

    fun consumeSnackbar() {
        _state.update { it.copy(snackbar = null) }
    }

    fun consumeDismiss() {
        _state.update { it.copy(dismiss = false) }
    }

    private fun updateTask(transform: (HermesTask) -> HermesTask) {
        val current = _state.value.task
        val updated = transform(current).copy(updatedAt = System.currentTimeMillis())
        _state.update {
            it.copy(
                task = updated,
                promptPreview = promptBuilder.build(updated, profileFor(updated.targetTool)),
            )
        }
    }

    private fun profileFor(target: TargetTool): AiToolProfile? =
        DefaultToolProfiles.byTargetTool(target)
}
