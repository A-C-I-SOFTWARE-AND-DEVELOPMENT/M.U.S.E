package com.aci.hermes.data.model

import kotlinx.serialization.Serializable
import java.util.UUID

@Serializable
enum class AuditSeverity { INFO, NOTICE, WARNING, CRITICAL }

/**
 * One entry on the proof / audit ledger. `proofHash` is the
 * deterministic fingerprint that lets a viewer confirm the entry hasn't
 * been tampered with. We store the hash inline so the UI does not need
 * to recompute it on every render.
 */
@Serializable
data class AuditEvent(
    val id: String = UUID.randomUUID().toString(),
    val actor: String = "system",
    val action: String = "",
    val target: String = "",
    val payloadSummary: String = "",
    val severity: AuditSeverity = AuditSeverity.INFO,
    val createdAt: Long = System.currentTimeMillis(),
    val proofHash: String = "",
    val approvalId: String? = null,
)
