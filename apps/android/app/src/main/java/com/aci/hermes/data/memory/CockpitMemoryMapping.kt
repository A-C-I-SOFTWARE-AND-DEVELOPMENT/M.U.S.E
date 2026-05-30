package com.aci.hermes.data.memory

import com.aci.hermes.data.cockpit.CockpitMemoryItem
import java.time.Instant
import java.time.OffsetDateTime

/**
 * Maps the cockpit wire model ([CockpitMemoryItem]) to the rich UI domain
 * model ([MemoryItem]). The wire enums are raw Strings; unknown values map
 * to an honest default rather than crashing. ISO-8601 timestamps become
 * epoch-millis (the domain model's representation).
 *
 * No fabrication: a field the server omits stays null/0, and an
 * unrecognised category becomes [MemoryCategory.UNCATEGORIZED].
 */

fun CockpitMemoryItem.toDomain(): MemoryItem {
    val created = parseIsoToMillis(createdAt)
        ?: parseIsoToMillis(provenance.recordedAt)
        ?: 0L
    return MemoryItem(
        id = id,
        category = enumByNameOrDefault(category, MemoryCategory.UNCATEGORIZED),
        title = title,
        content = content,
        durability = enumByNameOrDefault(durability, MemoryDurability.SESSION),
        confidence = enumByNameOrDefault(confidence, MemoryConfidence.MEDIUM),
        provenance = MemoryProvenance(
            source = provenance.source,
            sessionId = provenance.sessionId,
            recordedAt = parseIsoToMillis(provenance.recordedAt) ?: created,
            note = provenance.note,
        ),
        createdAt = created,
        updatedAt = parseIsoToMillis(updatedAt) ?: created,
        lastAccessedAt = parseIsoToMillis(lastAccessedAt),
        tags = tags,
        redacted = redacted,
        hidden = hidden,
    )
}

/** Parse an ISO-8601 timestamp (offset or `Z`) to epoch millis, or null. */
internal fun parseIsoToMillis(iso: String?): Long? {
    if (iso.isNullOrBlank()) return null
    return runCatching { OffsetDateTime.parse(iso).toInstant().toEpochMilli() }
        .recoverCatching { Instant.parse(iso).toEpochMilli() }
        .getOrNull()
}

internal inline fun <reified E : Enum<E>> enumByNameOrDefault(name: String?, default: E): E =
    enumValues<E>().firstOrNull { it.name.equals(name?.trim(), ignoreCase = true) } ?: default
