package com.aci.hermes.ui.screens.audit

/**
 * Owner-facing copy for empty + filtered states on the Audit surface.
 * Pure Kotlin so the screen and the JVM tests share one source of
 * truth. Audit is a proof surface for the owner — every line here
 * reinforces that secrets are redacted, history is owner-only, and
 * the screen never executes anything.
 */
object AuditEmptyStateCopy {

    const val GENUINELY_EMPTY =
        "No audit events yet. Every approved action, verification, and rollback " +
            "Jarvis runs will land here — secrets redacted, owner-only."

    const val FILTER_HIDES_ALL =
        "No audit events match the current filter. Clear filters to see the full " +
            "owner-only history."

    const val OWNER_NOTE_REDACTED =
        "Audit is owner-only. Secrets, API keys, and tokens are redacted before " +
            "they reach this screen."

    /**
     * Pick the right copy.
     * @param filterActive true when a search/filter is restricting the list.
     * @param totalRecords total in the underlying repository (post-redaction).
     */
    fun chooseFor(filterActive: Boolean, totalRecords: Int): String = when {
        totalRecords == 0 -> GENUINELY_EMPTY
        filterActive -> FILTER_HIDES_ALL
        else -> GENUINELY_EMPTY
    }

    /**
     * Defense-in-depth at the screen layer: any string about to be
     * shown in an audit empty/footer block goes through this guard
     * so a future copy edit can't accidentally embed a raw secret.
     */
    fun sanitizeForDisplay(value: String): String {
        if (value.isBlank()) return value
        // The repository already redacts via SecretRedactor; this is a
        // belt-and-braces check that catches obvious secret-shaped
        // substrings ("sk-…", "Bearer …") in case a copy edit ever
        // pastes one in.
        var out = value
        out = SECRET_SHAPES.fold(out) { acc, pattern ->
            pattern.replace(acc, "[REDACTED]")
        }
        return out
    }

    private val SECRET_SHAPES = listOf(
        Regex("""sk-[A-Za-z0-9_\-]{8,}"""),
        Regex("""Bearer\s+[A-Za-z0-9._\-]{8,}"""),
        Regex("""[A-Za-z0-9._\-]{20,}\.[A-Za-z0-9._\-]{20,}\.[A-Za-z0-9._\-]{20,}"""),
    )
}
