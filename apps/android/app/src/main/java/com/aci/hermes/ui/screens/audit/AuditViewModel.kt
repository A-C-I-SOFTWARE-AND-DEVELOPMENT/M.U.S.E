package com.aci.hermes.ui.screens.audit

import android.app.Application
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.audit.AuditRepository
import com.aci.hermes.data.model.AuditEntry
import com.aci.hermes.data.model.AuditKind
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

enum class AuditFilter { ALL, ACTIONS, APPROVALS, OVERRIDES, STOPS }

data class AuditUiState(
    val entries: List<AuditEntry> = emptyList(),
    val filter: AuditFilter = AuditFilter.ALL,
    val snackbar: String? = null,
)

class AuditViewModel(
    application: Application,
    private val audit: AuditRepository,
) : AndroidViewModel(application) {

    private val _state = MutableStateFlow(AuditUiState())
    val state: StateFlow<AuditUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            audit.items.collect { list ->
                _state.update { it.copy(entries = list) }
            }
        }
    }

    fun setFilter(filter: AuditFilter) {
        _state.update { it.copy(filter = filter) }
    }

    fun filtered(): List<AuditEntry> {
        val s = _state.value
        return s.entries.filter { entry ->
            when (s.filter) {
                AuditFilter.ALL -> true
                AuditFilter.ACTIONS -> entry.kind == AuditKind.ACTION_TAKEN
                AuditFilter.APPROVALS -> entry.kind == AuditKind.APPROVAL_GRANTED ||
                    entry.kind == AuditKind.APPROVAL_DENIED
                AuditFilter.OVERRIDES -> entry.kind == AuditKind.OVERRIDE_USED
                AuditFilter.STOPS -> entry.kind == AuditKind.EMERGENCY_STOP_ENGAGED ||
                    entry.kind == AuditKind.EMERGENCY_STOP_RELEASED
            }
        }
    }

    fun exportToClipboard() {
        val ctx = getApplication<Application>()
        val cm = ctx.getSystemService(Context.CLIPBOARD_SERVICE) as? ClipboardManager ?: return
        val md = audit.exportMarkdown()
        cm.setPrimaryClip(ClipData.newPlainText("Jarvis Prime audit", md))
        _state.update { it.copy(snackbar = "Audit log copied to clipboard.") }
    }

    fun consumeSnackbar() {
        _state.update { it.copy(snackbar = null) }
    }
}
