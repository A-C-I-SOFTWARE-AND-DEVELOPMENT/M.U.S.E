package com.aci.hermes.data.redaction

/**
 * Best-effort PII / secret redaction for content that flows into memory,
 * social intelligence and audit. Intentionally conservative — false
 * positives are acceptable, false negatives are not.
 *
 * Pure Kotlin, no Android dependencies, so it can be unit-tested off
 * the device.
 */
object Redactor {

    private const val MASK = "[redacted]"

    private val emailRegex = Regex(
        "[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}"
    )

    // International + local phone numbers (very generous).
    private val phoneRegex = Regex(
        "(?:\\+?\\d[\\d\\-\\s().]{7,}\\d)"
    )

    private val ipv4Regex = Regex(
        "\\b(?:\\d{1,3}\\.){3}\\d{1,3}\\b"
    )

    // 16-19 digit card-like sequences.
    private val cardRegex = Regex("\\b(?:\\d[ -]?){13,18}\\d\\b")

    // OpenAI / Anthropic / generic API key shapes.
    private val apiKeyRegex = Regex(
        "(?i)(?:sk|api|key|token|bearer)[-_]?[A-Za-z0-9_\\-]{16,}"
    )

    // GitHub fine-grained tokens, classic PATs and OAuth tokens.
    private val githubTokenRegex = Regex("gh[pousr]_[A-Za-z0-9]{20,}")

    private val secretBlockRegex = Regex(
        "(?i)(password|passwd|secret|token|api[_ -]?key)\\s*[:=]\\s*\\S+"
    )

    private val handleRegex = Regex("(?<![A-Za-z0-9_])@[A-Za-z0-9_.\\-]{2,}")

    /**
     * Redact a freeform string. Returns the redacted text and the set
     * of field names (kinds) that were redacted, so callers can show
     * the user what was hidden without showing the actual values.
     */
    fun redact(input: String): RedactionResult {
        if (input.isBlank()) return RedactionResult(input, emptyList())
        val hits = mutableSetOf<String>()
        var out = input

        out = secretBlockRegex.replace(out) { hits += "secret"; "${it.groupValues[1]}: $MASK" }
        out = apiKeyRegex.replace(out) { hits += "api_key"; MASK }
        out = githubTokenRegex.replace(out) { hits += "github_token"; MASK }
        out = cardRegex.replace(out) { hits += "card_number"; MASK }
        out = emailRegex.replace(out) { hits += "email"; MASK }
        out = phoneRegex.replace(out) { hits += "phone"; MASK }
        out = ipv4Regex.replace(out) { hits += "ipv4"; MASK }
        out = handleRegex.replace(out) { hits += "handle"; MASK }

        return RedactionResult(out, hits.toList().sorted())
    }

    /** Token used in place of a personal name / identifier. */
    fun nameToken(rawName: String): String {
        if (rawName.isBlank()) return "subject:unknown"
        val initials = rawName.trim()
            .split(Regex("\\s+"))
            .take(2)
            .mapNotNull { it.firstOrNull()?.uppercaseChar()?.toString() }
            .joinToString("")
        val len = rawName.length.coerceAtMost(99)
        return "subject:${initials.ifBlank { "X" }}#$len"
    }
}

data class RedactionResult(val text: String, val redactedFields: List<String>)
