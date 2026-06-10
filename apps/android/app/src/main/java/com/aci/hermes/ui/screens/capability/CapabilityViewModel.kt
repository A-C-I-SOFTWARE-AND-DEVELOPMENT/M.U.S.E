package com.aci.hermes.ui.screens.capability

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.capability.CapabilityRepository
import com.aci.hermes.data.capability.RoutePreview
import com.aci.hermes.data.cockpit.CockpitResult
import com.aci.hermes.data.cockpit.CockpitSkill
import com.aci.hermes.data.cockpit.HermesCockpitClient
import com.aci.hermes.data.model.Capability
import com.aci.hermes.data.model.CapabilityCategory
import com.aci.hermes.data.orchestrator.HandoffLauncher
import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/** Sync state of the gateway's real installed skills (honest, never faked). */
sealed interface InstalledSkillsSync {
    data object Idle : InstalledSkillsSync
    data object NotPaired : InstalledSkillsSync
    data class Loaded(val count: Int) : InstalledSkillsSync
    data class Error(val message: String) : InstalledSkillsSync
}

data class CapabilityUiState(
    val query: String = "",
    val category: CapabilityCategory? = null,
    val includeAdvanced: Boolean = false,
    val results: List<Capability> = emptyList(),
    val totalCount: Int = 0,
    val selected: Capability? = null,
    val preview: RoutePreview? = null,
    val installedSkills: List<CockpitSkill> = emptyList(),
    val installedSync: InstalledSkillsSync = InstalledSkillsSync.Idle,
    val snackbar: String? = null,
)

/**
 * Drives the [CapabilityScreen]. Pure presentation logic — never
 * executes a tool, never opens a network connection. The only
 * side effects are clipboard writes (staging the prompt) and a
 * snackbar, both surfaced through [HandoffLauncher].
 */
class CapabilityViewModel(
    application: Application,
    private val repository: CapabilityRepository,
    private val logBuffer: LogBuffer,
    private val cockpitClient: HermesCockpitClient? = null,
) : AndroidViewModel(application) {

    private val _state = MutableStateFlow(CapabilityUiState())
    val state: StateFlow<CapabilityUiState> = _state.asStateFlow()

    init {
        refresh()
        loadInstalledSkills()
    }

    /**
     * Load the gateway's real installed skills (live), shown alongside the
     * curated catalog so the screen reflects what the backend actually has.
     * Honest states only — an unpaired/unreachable gateway shows no fake skills.
     */
    fun loadInstalledSkills() {
        val client = cockpitClient ?: return
        viewModelScope.launch {
            if (!client.isPaired()) {
                _state.update { it.copy(installedSkills = emptyList(), installedSync = InstalledSkillsSync.NotPaired) }
                return@launch
            }
            when (val res = client.skillsList()) {
                is CockpitResult.Success ->
                    _state.update {
                        it.copy(
                            installedSkills = res.value.skills,
                            installedSync = InstalledSkillsSync.Loaded(res.value.skills.size),
                        )
                    }
                is CockpitResult.Failure ->
                    _state.update { it.copy(installedSync = InstalledSkillsSync.Error("Gateway error ${res.httpStatus}: ${res.error.message}")) }
                is CockpitResult.Unreachable ->
                    _state.update { it.copy(installedSync = InstalledSkillsSync.Error(res.message)) }
            }
        }
    }

    fun setQuery(query: String) {
        _state.update { it.copy(query = query) }
        refresh()
    }

    fun setCategory(category: CapabilityCategory?) {
        _state.update { it.copy(category = category) }
        refresh()
    }

    fun setIncludeAdvanced(value: Boolean) {
        _state.update { it.copy(includeAdvanced = value) }
        refresh()
    }

    fun select(capability: Capability?) {
        if (capability == null) {
            _state.update { it.copy(selected = null, preview = null) }
            return
        }
        val preview = repository.previewRoute(capability)
        _state.update { it.copy(selected = capability, preview = preview) }
    }

    /**
     * Stage the selected capability's prompt on the clipboard. This
     * is the safe-invocation path — the prompt is *not* sent
     * anywhere; the user reviews it, then pastes into the chat /
     * gateway surface (or into another tool entirely).
     */
    fun stagePromptToClipboard() {
        val preview = _state.value.preview ?: return
        val capability = _state.value.selected ?: return
        val ok = HandoffLauncher.copyPrompt(
            context = getApplication(),
            label = "MUSE capability prompt",
            text = preview.staged,
        )
        if (ok) {
            logBuffer.info(
                "Capability",
                "Staged ${capability.id} prompt to clipboard (lane=${capability.route.lane})",
            )
            _state.update { it.copy(snackbar = "Prompt staged — paste into chat to dispatch") }
        } else {
            _state.update { it.copy(snackbar = "Could not access clipboard") }
        }
    }

    fun consumeSnackbar() {
        _state.update { it.copy(snackbar = null) }
    }

    private fun refresh() {
        val s = _state.value
        val results = repository.search(
            query = s.query,
            category = s.category,
            includeAdvanced = s.includeAdvanced,
        )
        _state.update {
            it.copy(
                results = results,
                totalCount = repository.all().size,
            )
        }
    }
}
