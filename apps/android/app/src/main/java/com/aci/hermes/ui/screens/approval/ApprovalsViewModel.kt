package com.aci.hermes.ui.screens.approval

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.approval.ApprovalRepository
import com.aci.hermes.data.audit.AuditRepository
import com.aci.hermes.data.emergency.EmergencyStopController
import com.aci.hermes.data.model.ApprovalCard
import com.aci.hermes.data.model.ApprovalSeverity
import com.aci.hermes.data.model.ApprovalStatus
import com.aci.hermes.data.model.AuditKind
import com.aci.hermes.data.model.JarvisNotificationKind
import com.aci.hermes.data.notifications.JarvisNotificationRepository
import com.aci.hermes.data.preferences.SettingsRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

enum class ApprovalsFilter { PENDING, DECIDED, ALL }

data class ApprovalsUiState(
    val pending: List<ApprovalCard> = emptyList(),
    val decided: List<ApprovalCard> = emptyList(),
    val filter: ApprovalsFilter = ApprovalsFilter.PENDING,
    val emergencyEngaged: Boolean = false,
    val requireCriticalPhrase: Boolean = true,
    val requireDoubleConfirmSerious: Boolean = true,
)

class ApprovalsViewModel(
    application: Application,
    private val approvals: ApprovalRepository,
    private val settings: SettingsRepository,
    private val audit: AuditRepository,
    private val notifications: JarvisNotificationRepository,
    private val emergencyStop: EmergencyStopController,
) : AndroidViewModel(application) {

    private val _state = MutableStateFlow(ApprovalsUiState())
    val state: StateFlow<ApprovalsUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            approvals.items.collect { list ->
                _state.update {
                    it.copy(
                        pending = list.filter { c -> c.status == ApprovalStatus.PENDING },
                        decided = list.filter { c -> c.status != ApprovalStatus.PENDING },
                    )
                }
            }
        }
        viewModelScope.launch {
            settings.criticalPhraseRequired.collect { v ->
                _state.update { it.copy(requireCriticalPhrase = v) }
            }
        }
        viewModelScope.launch {
            settings.doubleConfirmSerious.collect { v ->
                _state.update { it.copy(requireDoubleConfirmSerious = v) }
            }
        }
        viewModelScope.launch {
            emergencyStop.state.collect { es ->
                _state.update { it.copy(emergencyEngaged = es.engaged) }
            }
        }
    }

    fun setFilter(filter: ApprovalsFilter) {
        _state.update { it.copy(filter = filter) }
    }

    fun approve(card: ApprovalCard, notes: String? = null) {
        if (_state.value.emergencyEngaged) return
        viewModelScope.launch {
            approvals.approve(card.id, notes)
            audit.record(
                kind = AuditKind.APPROVAL_GRANTED,
                title = "Approved: ${card.title}",
                detail = buildAuditDetail(card, "approved", notes),
                relatedId = card.id,
            )
            notifications.add(
                kind = JarvisNotificationKind.SUCCESS,
                title = "Approval granted",
                body = card.title,
                actionTargetId = card.id,
            )
        }
    }

    fun deny(card: ApprovalCard, notes: String? = null) {
        viewModelScope.launch {
            approvals.deny(card.id, notes)
            audit.record(
                kind = AuditKind.APPROVAL_DENIED,
                title = "Denied: ${card.title}",
                detail = buildAuditDetail(card, "denied", notes),
                relatedId = card.id,
            )
        }
    }

    private fun buildAuditDetail(card: ApprovalCard, decision: String, notes: String?): String {
        val sb = StringBuilder()
        sb.appendLine("Severity: ${card.severity.name.lowercase()}")
        sb.appendLine("Decision: $decision")
        if (card.source != null) sb.appendLine("Source: ${card.source}")
        if (notes != null) sb.appendLine("Notes: $notes")
        if (card.impact != null) {
            sb.appendLine()
            sb.appendLine("Impact summary: ${card.impact.summary}")
            if (card.impact.rollbackPlan != null) sb.appendLine("Rollback: ${card.impact.rollbackPlan}")
        }
        return sb.toString().trim()
    }

    fun severityRequiresImpact(severity: ApprovalSeverity): Boolean =
        severity == ApprovalSeverity.SERIOUS || severity == ApprovalSeverity.CRITICAL
}
