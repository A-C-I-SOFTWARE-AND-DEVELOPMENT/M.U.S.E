package com.aci.hermes.data.social

import com.aci.hermes.data.model.PatternProvenance
import com.aci.hermes.data.model.PrivacyRisk
import com.aci.hermes.data.model.ProvenanceKind
import com.aci.hermes.data.model.SocialPattern

/**
 * The privacy boundary for muse Social Intelligence.
 *
 * muse is allowed to learn *abstract* speech patterns. It is
 * never allowed to store identity. This object detects and redacts:
 *
 *  - usernames / handles  (`@alice`, `u/alice`, `t.me/alice`)
 *  - real-name-shaped tokens ("Jane Doe")
 *  - email addresses, phone numbers
 *  - private / auth-walled URLs
 *
 * The redactor is intentionally over-eager. False positives degrade
 * to a generic `[redacted]` token; false negatives would leak
 * identity, which is the threat we're optimizing against. The same
 * redactor runs at both write and render time so that older stored
 * data also benefits from any tightening of the rules.
 */
object PrivacyRedactor {

    const val REDACTION_TOKEN = "[redacted]"

    private val handleRegex = Regex("(?<![\\w/])@[A-Za-z0-9_]{2,}")
    private val redditHandleRegex = Regex("\\b(?:u|r)/[A-Za-z0-9_]{2,}")
    private val platformHandleRegex = Regex(
        "\\b(?:t\\.me|twitter\\.com|x\\.com|instagram\\.com|tiktok\\.com|github\\.com|linkedin\\.com/in)/[A-Za-z0-9_.-]+",
        RegexOption.IGNORE_CASE,
    )
    private val emailRegex = Regex("[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}")
    private val phoneRegex = Regex("(?<!\\d)(?:\\+?\\d[\\s().-]?){7,}\\d(?!\\d)")
    private val realNameRegex = Regex("\\b([A-Z][a-z]{1,20})\\s+([A-Z][a-z]{1,20})\\b")

    // Words that look like name pairs but are common phrases. Add to
    // this list when a false positive ships — never silently broaden
    // the regex.
    private val nameWhitelist = setOf(
        "United States", "New York", "San Francisco", "Los Angeles",
        "Hong Kong", "South Korea", "South America", "North America",
        "Open Source", "Stack Overflow", "Github Actions",
    )

    // Placeholders left by the runtime's MemoryRedactor when it strips
    // identity from a stored memory before it reaches the UI.
    private val upstreamRedactionMarkers = listOf(
        "[identity]" to "identity",
        "[handle]" to "handle",
        "[email]" to "email",
        "[phone]" to "phone",
    )

    private val privateUrlMarkers = listOf(
        "auth=", "token=", "session=", "private=", "/dm/", "/messages/",
        "mail.google.com", "docs.google.com/", "/admin/", "/account/",
    )

    /**
     * Strip identity-bearing tokens from free-form text.
     *
     * Returns the redacted string. The result never contains
     * usernames, handles, emails, phone numbers, or `Firstname
     * Lastname`-shaped tokens.
     */
    fun redactIdentity(text: String): String {
        if (text.isBlank()) return text
        var out = text
        out = handleRegex.replace(out, REDACTION_TOKEN)
        out = redditHandleRegex.replace(out, REDACTION_TOKEN)
        out = platformHandleRegex.replace(out, REDACTION_TOKEN)
        out = emailRegex.replace(out, REDACTION_TOKEN)
        out = phoneRegex.replace(out, REDACTION_TOKEN)
        out = realNameRegex.replace(out) { match ->
            if (nameWhitelist.contains(match.value)) match.value else REDACTION_TOKEN
        }
        return out
    }

    /** True if [text] still contains identity tokens after a redaction pass would run. */
    fun containsIdentity(text: String): Boolean {
        if (text.isBlank()) return false
        return redactIdentity(text) != text
    }

    /**
     * List the kinds of identity tokens present in [text]. The result
     * is used by [classifyRisk] and by [SocialPattern.identityFlags]
     * so the UI can show "private identity flagged" for the user.
     */
    fun identityFlagsIn(text: String): List<String> {
        if (text.isBlank()) return emptyList()
        val flags = mutableListOf<String>()
        if (handleRegex.containsMatchIn(text)) flags.add("handle")
        if (redditHandleRegex.containsMatchIn(text)) flags.add("platform_handle")
        if (platformHandleRegex.containsMatchIn(text)) flags.add("platform_url")
        if (emailRegex.containsMatchIn(text)) flags.add("email")
        if (phoneRegex.containsMatchIn(text)) flags.add("phone")
        val realNameMatch = realNameRegex.findAll(text).any { match ->
            !nameWhitelist.contains(match.value)
        }
        if (realNameMatch) flags.add("real_name")
        // The runtime's MemoryRedactor replaces stripped identity with
        // placeholder markers before data reaches the UI. Their
        // presence means identity was found in the source and removed —
        // surface that as a flag so the pattern is still labeled
        // "private identity flagged" even though the literal value is
        // already gone.
        upstreamRedactionMarkers.forEach { (marker, flag) ->
            if (text.contains(marker, ignoreCase = true) && !flags.contains(flag)) {
                flags.add(flag)
            }
        }
        return flags
    }

    /**
     * Walk a provenance list and drop entries that look private or
     * auth-walled, redact identity from any free-form fields, and
     * never let a real URL through if it points at a personal
     * profile. The resulting list is safe to display.
     */
    fun sanitizeProvenance(entries: List<PatternProvenance>): List<PatternProvenance> {
        return entries.mapNotNull { entry ->
            val url = entry.sourceUrl?.trim().orEmpty()
            val looksPrivate = url.isNotEmpty() && (
                privateUrlMarkers.any { url.contains(it, ignoreCase = true) } ||
                    platformHandleRegex.containsMatchIn(url)
                )
            if (looksPrivate) return@mapNotNull null
            entry.copy(
                sourceTitle = redactIdentity(entry.sourceTitle),
                sourceUrl = entry.sourceUrl?.let { redactIdentity(it) },
                note = entry.note?.let { redactIdentity(it) },
            )
        }
    }

    /**
     * Privacy risk is a function of how much identity slipped through
     * redaction. The UI uses this to color the chip and to gate
     * display: HIGH always hides the summary behind a warning.
     */
    fun classifyRisk(flags: List<String>): PrivacyRisk = when {
        flags.isEmpty() -> PrivacyRisk.LOW
        flags.size == 1 && flags.first() == "real_name" -> PrivacyRisk.MEDIUM
        else -> PrivacyRisk.HIGH
    }

    /**
     * Sanitize a [SocialPattern] before persistence. Identity tokens
     * in any free-form field are replaced with [REDACTION_TOKEN]; the
     * stored flags + risk reflect what was originally in the input so
     * the user can see why their pattern was redacted.
     */
    fun sanitize(pattern: SocialPattern): SocialPattern {
        val rawText = listOf(
            pattern.title,
            pattern.summary,
            pattern.safeUsage,
            pattern.unsafeUsage,
        ).joinToString(" ")
        val flags = identityFlagsIn(rawText)
        val risk = classifyRisk(flags)
        return pattern.copy(
            title = redactIdentity(pattern.title),
            summary = redactIdentity(pattern.summary),
            safeUsage = redactIdentity(pattern.safeUsage),
            unsafeUsage = redactIdentity(pattern.unsafeUsage),
            provenance = sanitizeProvenance(
                pattern.provenance.filter { it.sourceKind != ProvenanceKind.USER_TAUGHT || !containsIdentity(it.sourceTitle) },
            ),
            privacyRisk = risk,
            identityFlags = flags,
            updatedAt = System.currentTimeMillis(),
        )
    }
}
