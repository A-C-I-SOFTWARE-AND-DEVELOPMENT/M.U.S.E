package com.aci.hermes.data.ledger

import com.aci.hermes.data.audit.auditEnum
import com.aci.hermes.data.cockpit.CockpitLedgerDiff
import com.aci.hermes.data.cockpit.CockpitLedgerEvent
import com.aci.hermes.data.cockpit.CockpitLedgerEventDetail
import com.aci.hermes.data.cockpit.CockpitLedgerEvidence
import com.aci.hermes.data.cockpit.CockpitLedgerRollback
import com.aci.hermes.data.model.audit.RiskTier
import com.aci.hermes.data.model.ledger.LedgerCategory
import com.aci.hermes.data.model.ledger.LedgerDiff
import com.aci.hermes.data.model.ledger.LedgerEvent
import com.aci.hermes.data.model.ledger.LedgerEventDetail
import com.aci.hermes.data.model.ledger.LedgerEvidence
import com.aci.hermes.data.model.ledger.LedgerRollback
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive

/**
 * Maps the cockpit ledger wire models (`data.cockpit.CockpitLedger*`) to the
 * domain models in `data.model.ledger`. Enum-like wire strings map by name
 * with an honest fallback (unknown → safe default); the `payload` JsonObject
 * is flattened to readable key→value pairs for the detail screen.
 */

fun CockpitLedgerEvent.toDomain(): LedgerEvent = LedgerEvent(
    id = id,
    jobId = jobId,
    index = index,
    timestamp = timestamp,
    category = LedgerCategory.fromWire(category),
    kind = kind,
    worker = worker,
    riskTier = auditEnum(riskTier, RiskTier.LOW),
    summary = summary,
    files = files,
    hasRollback = hasRollback,
    hasEvidence = hasEvidence,
    hasDiff = hasDiff,
)

fun CockpitLedgerEventDetail.toDomain(): LedgerEventDetail = LedgerEventDetail(
    id = id,
    jobId = jobId,
    index = index,
    timestamp = timestamp,
    category = LedgerCategory.fromWire(category),
    kind = kind,
    worker = worker,
    riskTier = auditEnum(riskTier, RiskTier.LOW),
    summary = summary,
    files = files,
    payload = payload.flatten(),
    evidence = evidence.map { it.toDomain() },
    diff = diff?.toDomain(),
    rollback = rollback?.toDomain(),
    rollbackAvailable = rollbackAvailable,
)

private fun CockpitLedgerEvidence.toDomain(): LedgerEvidence = LedgerEvidence(
    id = id,
    title = title,
    body = body,
    sourcePath = sourcePath,
)

private fun CockpitLedgerDiff.toDomain(): LedgerDiff = LedgerDiff(
    body = body,
    files = files,
)

private fun CockpitLedgerRollback.toDomain(): LedgerRollback = LedgerRollback(
    summary = summary,
    steps = steps,
)

/** Flatten a redacted payload JsonObject into stable, displayable pairs. */
private fun JsonObject.flatten(): List<Pair<String, String>> =
    entries.map { (key, value) ->
        val rendered = (value as? JsonPrimitive)?.content ?: value.toString()
        key to rendered
    }
