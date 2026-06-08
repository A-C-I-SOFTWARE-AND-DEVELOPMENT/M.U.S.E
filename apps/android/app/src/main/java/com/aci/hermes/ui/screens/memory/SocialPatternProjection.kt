package com.aci.hermes.ui.screens.memory

import com.aci.hermes.data.memory.MemoryItem
import com.aci.hermes.data.model.PatternProvenance
import com.aci.hermes.data.model.ProvenanceKind
import com.aci.hermes.data.model.SocialPattern
import com.aci.hermes.data.model.SocialPatternKind

/**
 * Projects a generic [MemoryItem] in the SOCIAL_SPEECH_PATTERN
 * category into the structured [SocialPattern] view model that the
 * rich [SocialPatternCard] and the social section of [MemoryDetail]
 * render.
 *
 * There is a single source of truth for memory — [com.aci.hermes.data.memory.MemoryRepository].
 * Social speech patterns are stored as ordinary [MemoryItem]s and the
 * runtime's [com.aci.hermes.data.memory.MemoryRedactor] has already
 * stripped identity by the time an item reaches the UI. This object
 * does not store anything; it only derives the abstract,
 * privacy-safe structure the Social Intelligence UI needs:
 *
 *  - **privacy risk / identity flags** — derived from the redaction
 *    markers the runtime left behind (`[identity]`, `[handle]`,
 *    `[email]`, `[phone]`). Their presence means identity was found
 *    in the source and stripped, which the card surfaces as
 *    "private identity flagged" and escalates to HIGH risk.
 *  - **safe / unsafe usage** — the abstract guidance for the pattern.
 *    Unsafe usage is the universal MUSE boundary (never
 *    impersonate, never attach identity, never manipulate); safe
 *    usage is tailored to the inferred [SocialPatternKind].
 *  - **provenance** — mapped from the item's single source into the
 *    public-source provenance list.
 *
 * [SocialPattern]'s own constructor + the model-level
 * [com.aci.hermes.data.social.PrivacyRedactor] run on the result, so
 * even if a marker is missed here the card still re-sanitizes before
 * display.
 */
object SocialPatternProjection {

    private val redactionMarkers = mapOf(
        "[identity]" to "identity",
        "[handle]" to "handle",
        "[email]" to "email",
        "[phone]" to "phone",
    )

    fun from(item: MemoryItem): SocialPattern {
        val kind = inferKind(item)
        val flags = identityFlags(item)
        return SocialPattern(
            id = item.id,
            title = item.title,
            kind = kind,
            summary = item.content,
            safeUsage = safeUsageFor(kind),
            unsafeUsage = UNSAFE_USAGE,
            provenance = provenanceFrom(item),
            // privacyRisk + identityFlags are recomputed by
            // SocialPattern's redactor on the text; we seed the flags
            // we already know from the runtime's redaction markers so
            // "private identity flagged" shows even though the literal
            // identity is gone from the text.
            identityFlags = flags,
            createdAt = item.createdAt,
            updatedAt = item.updatedAt,
        )
    }

    /** Identity flags inferred from the runtime's redaction markers. */
    fun identityFlags(item: MemoryItem): List<String> {
        val haystack = "${item.title} ${item.content}"
        return redactionMarkers.entries
            .filter { haystack.contains(it.key, ignoreCase = true) }
            .map { it.value }
            .distinct()
    }

    private fun inferKind(item: MemoryItem): SocialPatternKind {
        // Explicit tag wins (e.g. tag "mobile_reply" or "MOBILE_REPLY").
        item.tags.forEach { tag ->
            val normalized = tag.trim().uppercase().replace(' ', '_').replace('-', '_')
            SocialPatternKind.entries.firstOrNull { it.name == normalized }?.let { return it }
        }
        val text = "${item.title} ${item.content}".lowercase()
        return when {
            text.contains("mobile") || text.contains("phone reply") || text.contains("on the go") -> SocialPatternKind.MOBILE_REPLY
            text.contains("disagree") || text.contains("pushback") || text.contains("conflict") -> SocialPatternKind.DISAGREEMENT
            text.contains("trust") || text.contains("rapport") -> SocialPatternKind.TRUST_BUILDING
            text.contains("support") || text.contains("reassur") || text.contains("help") -> SocialPatternKind.SUPPORT
            text.contains("triage") || text.contains("debug") || text.contains("technical") || text.contains("incident") -> SocialPatternKind.TECHNICAL_TRIAGE
            else -> SocialPatternKind.COMMUNICATION
        }
    }

    private fun safeUsageFor(kind: SocialPatternKind): String = when (kind) {
        SocialPatternKind.MOBILE_REPLY ->
            "Mirror the brevity and informal tone when replying from a phone. Keep links to public docs."
        SocialPatternKind.DISAGREEMENT ->
            "Use the abstract structure for stating disagreement calmly and with reasons. Stay on the idea, not the person."
        SocialPatternKind.TRUST_BUILDING ->
            "Apply the pattern's cadence for building rapport — acknowledge, then add value. Keep it generic."
        SocialPatternKind.SUPPORT ->
            "Reuse the supportive phrasing shape when reassuring someone. Keep it warm and non-specific."
        SocialPatternKind.TECHNICAL_TRIAGE ->
            "Follow the triage ordering (symptom, scope, next step) when responding to technical issues."
        SocialPatternKind.COMMUNICATION ->
            "Apply the abstract communication style only. Keep it generic and public-safe."
    }

    private fun provenanceFrom(item: MemoryItem): List<PatternProvenance> {
        val source = item.provenance.source.trim()
        if (source.isEmpty()) return emptyList()
        val kind = if (source.contains("mode") || source.contains("session") || source.contains("companion")) {
            ProvenanceKind.USER_TAUGHT
        } else {
            ProvenanceKind.PUBLIC_DOC
        }
        return listOf(
            PatternProvenance(
                sourceTitle = source,
                sourceKind = kind,
                note = item.provenance.note,
            ),
        )
    }

    /**
     * The universal MUSE boundary for every social speech
     * pattern. This mirrors the mission's blocked list and never
     * changes per-pattern.
     */
    const val UNSAFE_USAGE: String =
        "Never impersonate a specific person, attach this pattern to a real identity, or use it to " +
            "manipulate. No usernames, real names, private profile data, or copied raw comments."
}
