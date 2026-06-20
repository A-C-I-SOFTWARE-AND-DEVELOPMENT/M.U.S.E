package com.aci.hermes.data.audit

/**
 * Redacts secret-like substrings before audit material is rendered in
 * the UI or copied to the clipboard. muse guarantees the audit
 * surface never leaks credentials even if a worker accidentally logged
 * one in a diff or command output.
 *
 * Detection is intentionally conservative: it favors false positives
 * (over-redaction) over false negatives, because the cost of leaking
 * one real secret is much higher than the cost of redacting an
 * innocuous lookalike.
 */
object SecretRedactor {

    const val REDACTION_MARKER = "[REDACTED]"

    private val keyValueAssignmentPattern = Regex(
        pattern = """(?ix)
            (?<key>
              (?:[A-Z][A-Z0-9_]*_)?
              (?:api[_-]?key|secret|token|password|passwd|pwd|access[_-]?key|
                 private[_-]?key|client[_-]?secret|auth|bearer|session)
              [A-Z0-9_]*
            )
            (?<delim>\s*[:=]\s*)
            (?<quote>["']?)
            (?<value>[^\s"',;]+)
            \k<quote>
        """,
    )

    private val authorizationHeaderPattern = Regex(
        pattern = """(?i)(authorization\s*:\s*)(bearer\s+|basic\s+)?([A-Za-z0-9+/=._\-]{12,})""",
    )

    private val providerTokenPatterns = listOf(
        Regex("""sk-(?:proj-|live-|test-)?[A-Za-z0-9\-_]{20,}"""),
        Regex("""ghp_[A-Za-z0-9]{20,}"""),
        Regex("""gho_[A-Za-z0-9]{20,}"""),
        Regex("""github_pat_[A-Za-z0-9_]{20,}"""),
        Regex("""xox[abprs]-[A-Za-z0-9\-]{10,}"""),
        Regex("""AKIA[0-9A-Z]{16}"""),
        Regex("""ASIA[0-9A-Z]{16}"""),
        Regex("""AIza[0-9A-Za-z\-_]{35}"""),
    )

    private val jwtPattern = Regex(
        pattern = """eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}""",
    )

    private val privateKeyBlockPattern = Regex(
        pattern = """-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----""",
    )

    fun redact(input: String?): String {
        if (input.isNullOrEmpty()) return ""
        var result: String = input

        result = privateKeyBlockPattern.replace(result, REDACTION_MARKER)
        result = jwtPattern.replace(result, REDACTION_MARKER)
        providerTokenPatterns.forEach { result = it.replace(result, REDACTION_MARKER) }

        result = authorizationHeaderPattern.replace(result) { match ->
            val token = match.groupValues[3]
            if (token == REDACTION_MARKER) match.value
            else match.groupValues[1] + match.groupValues[2] + REDACTION_MARKER
        }

        result = keyValueAssignmentPattern.replace(result) { match ->
            val value = match.groups["value"]?.value
            if (value == REDACTION_MARKER) return@replace match.value
            val key = match.groups["key"]?.value ?: return@replace match.value
            val delim = match.groups["delim"]?.value ?: "="
            val quote = match.groups["quote"]?.value.orEmpty()
            "$key$delim$quote$REDACTION_MARKER$quote"
        }

        return result
    }

    fun containsSecret(input: String?): Boolean {
        if (input.isNullOrEmpty()) return false
        if (privateKeyBlockPattern.containsMatchIn(input)) return true
        if (jwtPattern.containsMatchIn(input)) return true
        if (providerTokenPatterns.any { it.containsMatchIn(input) }) return true
        if (authorizationHeaderPattern.findAll(input).any { it.groupValues[3] != REDACTION_MARKER }) return true
        return keyValueAssignmentPattern.findAll(input).any { it.groups["value"]?.value != REDACTION_MARKER }
    }
}
