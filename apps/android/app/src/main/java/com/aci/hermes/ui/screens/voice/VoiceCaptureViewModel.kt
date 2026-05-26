package com.aci.hermes.ui.screens.voice

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.gateway.GatewayEventSpine
import com.aci.hermes.data.model.HermesTask
import com.aci.hermes.data.model.TaskStatus
import com.aci.hermes.data.model.TaskType
import com.aci.hermes.data.orchestrator.HermesTaskRepository
import com.aci.hermes.data.redaction.Redactor
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class VoiceUiState(
    val listening: Boolean = false,
    val transcript: String = "",
    val redacted: String = "",
    val redactedFields: List<String> = emptyList(),
    val permissionEducationShown: Boolean = true,
    val recognizerAvailable: Boolean = true,
    val createdTaskId: String? = null,
)

class VoiceCaptureViewModel(
    private val spine: GatewayEventSpine,
    private val tasksRepo: HermesTaskRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(VoiceUiState())
    val state: StateFlow<VoiceUiState> = _state.asStateFlow()

    fun setRecognizerAvailable(value: Boolean) {
        _state.update { it.copy(recognizerAvailable = value) }
    }

    fun setListening(value: Boolean) {
        _state.update { it.copy(listening = value) }
    }

    fun onTranscript(text: String) {
        val redaction = Redactor.redact(text)
        _state.update {
            it.copy(
                transcript = text,
                redacted = redaction.text,
                redactedFields = redaction.redactedFields,
            )
        }
    }

    fun dismissEducation() {
        _state.update { it.copy(permissionEducationShown = false) }
    }

    fun saveAsTask() {
        val text = _state.value.redacted.trim()
        if (text.isEmpty()) return
        viewModelScope.launch {
            val task = tasksRepo.upsert(
                HermesTask(
                    title = text.lineSequence().first().take(80),
                    description = text,
                    taskType = TaskType.PLANNING,
                    status = TaskStatus.DRAFT,
                )
            )
            spine.current()?.submitVoiceTranscript(text)
            _state.update { it.copy(createdTaskId = task.id) }
        }
    }

    fun consumeCreatedTask() {
        _state.update { it.copy(createdTaskId = null) }
    }
}
