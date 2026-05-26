package com.aci.hermes.data.audit

import com.aci.hermes.data.model.AuditEvent
import com.aci.hermes.data.redaction.Redactor
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlin.math.abs

class AuditRepository {

    private val _events = MutableStateFlow<List<AuditEvent>>(emptyList())
    val events: StateFlow<List<AuditEvent>> = _events.asStateFlow()

    fun append(raw: AuditEvent): AuditEvent {
        val redacted = raw.copy(payloadSummary = Redactor.redact(raw.payloadSummary).text)
        val withHash = if (redacted.proofHash.isBlank()) {
            redacted.copy(proofHash = proofHash(redacted))
        } else redacted
        _events.value = listOf(withHash) + _events.value
        return withHash
    }

    fun byId(id: String): AuditEvent? = _events.value.firstOrNull { it.id == id }

    fun clear() { _events.value = emptyList() }

    private fun proofHash(event: AuditEvent): String {
        val seed = "${event.actor}|${event.action}|${event.target}|${event.payloadSummary}|${event.createdAt}".hashCode()
        return "0x" + abs(seed.toLong()).toString(16).padStart(8, '0')
    }
}
