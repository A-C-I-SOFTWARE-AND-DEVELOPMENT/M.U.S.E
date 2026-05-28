package com.aci.hermes.data.automation

/**
 * Resolves a spoken app name ("facebook", "the fb app", "insta") to an
 * installed package. The fuzzy name-matching is pure and unit-tested;
 * the Android-specific package enumeration is injected as a list of
 * [InstalledApp] so the matcher never touches `PackageManager` directly.
 *
 * The accessibility service builds the [InstalledApp] list from
 * `PackageManager.queryIntentActivities(LAUNCHER)` and passes it in.
 */
class AppTargetResolver(private val installed: List<InstalledApp>) {

    data class InstalledApp(
        val packageName: String,
        val label: String,
        /** On-screen icon bounds, when the launcher is currently visible. */
        val iconBounds: ScreenRect? = null,
    )

    /**
     * Best match for [query], or null if nothing scores above the floor.
     * Scoring favors, in order: exact label, label/query prefix, token
     * containment, then package-name containment.
     */
    fun resolve(query: String): ResolvedTarget? {
        val q = normalize(query)
        if (q.isEmpty()) return null

        val expanded = ALIASES[q] ?: q
        var best: InstalledApp? = null
        var bestScore = 0

        for (app in installed) {
            val score = score(app, expanded, q)
            if (score > bestScore) {
                bestScore = score
                best = app
            }
        }
        if (best == null || bestScore < MIN_SCORE) return null
        return ResolvedTarget(
            label = best.label,
            bounds = best.iconBounds,
            packageName = best.packageName,
        )
    }

    private fun score(app: InstalledApp, expanded: String, raw: String): Int {
        val label = normalize(app.label)
        val pkg = app.packageName.lowercase()
        return when {
            label == expanded || label == raw -> 100
            label.startsWith(expanded) || expanded.startsWith(label) -> 80
            tokens(label).any { it == expanded || it == raw } -> 70
            expanded in label || raw in label -> 55
            // package id often carries the real brand ("com.facebook.katana")
            pkg.split('.').any { it == expanded || it == raw } -> 50
            expanded in pkg -> 35
            else -> 0
        }
    }

    private fun normalize(s: String): String =
        s.trim().lowercase().filter { it.isLetterOrDigit() || it == ' ' }.trim()

    private fun tokens(s: String): List<String> = s.split(' ').filter { it.isNotBlank() }

    companion object {
        const val MIN_SCORE = 35

        /** Common nicknames → canonical query the scorer matches on. */
        val ALIASES: Map<String, String> = mapOf(
            "fb" to "facebook",
            "insta" to "instagram",
            "ig" to "instagram",
            "yt" to "youtube",
            "whatsapp" to "whatsapp",
            "wa" to "whatsapp",
            "x" to "twitter",
            "tweet" to "twitter",
            "messages" to "messages",
            "text" to "messages",
            "gmail" to "gmail",
            "mail" to "gmail",
            "maps" to "maps",
            "gmaps" to "maps",
        )
    }
}
