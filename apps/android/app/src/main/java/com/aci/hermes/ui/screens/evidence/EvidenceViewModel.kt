package com.aci.hermes.ui.screens.evidence

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.evidence.EvidenceItem
import com.aci.hermes.data.evidence.EvidenceRepository
import com.aci.hermes.data.evidence.EvidenceSync
import com.aci.hermes.data.evidence.EvidenceVerification
import com.aci.hermes.data.evidence.PromoteOutcome
import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class EvidenceUiState(
    val query: String = "",
    val searchActive: Boolean = false,
    val items: List<EvidenceItem> = emptyList(),
    val selected: EvidenceItem? = null,
    val verification: EvidenceVerification? = null,
    /** Set when a promotion was rejected for an owner-gated reason; drives the
     *  explicit owner-authorization dialog (the phrase is never sent on a tap). */
    val authPromptItem: EvidenceItem? = null,
    val snackbar: String? = null,
    val sync: EvidenceSync = EvidenceSync.Idle,
)

/** Owner authorization phrase — only ever sent after an explicit confirmation. */
private const val OWNER_AUTHORIZATION_PHRASE = "Yes, with authorization."

/**
 * Drives the Evidence screen. Mirrors `MemoryViewModel`: collects the
 * repository flows and exposes one immutable [EvidenceUiState].
 *
 * Two behaviours worth calling out:
 * - **Search mode** renders `repository.hits` (mapped to display items), so a
 *   query shows ranked results rather than the stale browse list.
 * - **Promotion never auto-authorizes.** A normal Promote tap sends no owner
 *   phrase; if the gateway rejects for an owner-gated reason, an explicit
 *   authorization dialog is raised and only an explicit confirm re-sends the
 *   phrase. Hard rejections (secret / chain-of-thought) are reported, not
 *   offered for override.
 */
class EvidenceViewModel(
    private val repository: EvidenceRepository,
    private val logBuffer: LogBuffer,
) : ViewModel() {

    private val _state = MutableStateFlow(EvidenceUiState())
    val state: StateFlow<EvidenceUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            repository.items.collect { recompute() }
        }
        viewModelScope.launch {
            repository.hits.collect { recompute() }
        }
        viewModelScope.launch {
            repository.sync.collect { sync -> _state.update { it.copy(sync = sync) } }
        }
        refresh()
    }

    fun refresh() {
        viewModelScope.launch { repository.refresh() }
    }

    fun setQuery(q: String) {
        _state.update { it.copy(query = q) }
    }

    fun search() {
        val q = _state.value.query.trim()
        _state.update { it.copy(searchActive = q.isNotEmpty()) }
        recompute()
        viewModelScope.launch {
            if (q.isEmpty()) repository.refresh() else repository.search(q)
        }
    }

    /** The list to display: ranked hits in search mode, else the browse list. */
    private fun recompute() {
        val list = if (_state.value.searchActive) {
            repository.hits.value.map { it.toItem() }
        } else {
            repository.items.value
        }
        _state.update { it.copy(items = list) }
    }

    fun open(item: EvidenceItem) {
        _state.update { it.copy(selected = item) }
    }

    fun closeDetail() {
        _state.update { it.copy(selected = null) }
    }

    fun verify(claim: String) {
        if (claim.isBlank()) return
        viewModelScope.launch {
            val result = repository.verify(listOf(claim), query = claim)
            _state.update {
                it.copy(
                    verification = result,
                    snackbar = if (result == null) "Verify needs a paired gateway" else null,
                )
            }
        }
    }

    fun clearVerification() {
        _state.update { it.copy(verification = null) }
    }

    /**
     * Promote an item to durable memory. A normal call sends **no** owner
     * phrase; the gateway promotes high-trust items and honestly rejects
     * low-confidence/unverified ones. On an owner-gated rejection we raise
     * [EvidenceUiState.authPromptItem] so the owner can explicitly authorize.
     */
    fun promote(item: EvidenceItem, authorization: String? = null) {
        viewModelScope.launch {
            when (val outcome = repository.promote(item.id, authorization)) {
                is PromoteOutcome.Promoted -> {
                    logBuffer.info(TAG, "Promoted ${item.id} -> memory ${outcome.nodeId}")
                    _state.update {
                        it.copy(snackbar = "Promoted to memory", selected = null, authPromptItem = null)
                    }
                }
                is PromoteOutcome.Rejected -> {
                    val why = outcome.reasons.firstOrNull() ?: "rejected by memory policy"
                    logBuffer.info(TAG, "Promote rejected ${item.id}: $why")
                    if (authorization == null && isOwnerGated(outcome.reasons)) {
                        // Don't auto-send the phrase — ask the owner explicitly.
                        _state.update { it.copy(authPromptItem = item) }
                    } else {
                        _state.update { it.copy(snackbar = "Not promoted: $why", authPromptItem = null) }
                    }
                }
                is PromoteOutcome.Unreachable ->
                    _state.update { it.copy(snackbar = "Gateway unreachable: ${outcome.message}") }
                PromoteOutcome.NotLive ->
                    _state.update { it.copy(snackbar = "Promotion needs a paired gateway") }
            }
        }
    }

    /** Owner explicitly authorized the pending promotion in the dialog. */
    fun confirmAuthorizedPromote() {
        val item = _state.value.authPromptItem ?: return
        _state.update { it.copy(authPromptItem = null) }
        promote(item, OWNER_AUTHORIZATION_PHRASE)
    }

    fun cancelAuthPrompt() {
        _state.update { it.copy(authPromptItem = null) }
    }

    fun consumeSnackbar() {
        _state.update { it.copy(snackbar = null) }
    }

    private companion object {
        const val TAG = "Evidence"

        /**
         * True when a rejection is an owner-gate the owner can override with the
         * phrase (low confidence / missing approval) — NOT a hard policy block
         * (secret / chain-of-thought), which the phrase can never bypass.
         */
        fun isOwnerGated(reasons: List<String>): Boolean {
            val joined = reasons.joinToString(" ").lowercase()
            val hardBlock = "secret" in joined || "chain-of-thought" in joined || "chain of thought" in joined
            if (hardBlock) return false
            return "owner" in joined || "confidence" in joined || "approval" in joined || "provenance" in joined
        }
    }
}
