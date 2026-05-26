package com.aci.hermes.data.memory

/**
 * Privacy and safety filter applied to every memory item before it
 * reaches the UI. The rules enforced here are the ones the spec
 * demands of the Memory screen:
 *
 *  - Secrets (API keys, tokens, passwords, bearer values, OAuth
 *    fragments, long hex/base64 blobs that look like credentials)
 *    are redacted at display time. The owner sees a placeholder
 *    instead of the real value.
 *  - Social speech patterns are *abstract patterns* — they must
 *    never carry a username, handle, real name, or phone/email
 *    identity through to the display. Identities are stripped
 *    even if the underlying store contains them.
 *  - Temporary emotions (mood spikes captured for a session) must
 *    not be promoted to durable memory. We surface them as
 *    [MemoryDurability.EPHEMERAL] regardless of what the source
 *    claims, so the UI can show them in their proper bucket.
 *
 * Pure functions; no Android dependencies; covered by unit tests.
 */
object MemoryRedactor {

    private const val REDACTED = "███ redacted ███"

    private val secretKeyHints = listOf(
        "api_key", "apikey", "api key",
        "secret", "token", "password", "passwd",
        "bearer ", "authorization:", "auth:",
        "client_secret", "private_key", "ssh-rsa",
        "aws_secret", "aws_access_key", "sk-",
    )

    private val identityHints = listOf(
        "username", "user name", "user_name",
        "handle:", "@",
        "real name", "full name", "name:",
        "email:", "phone:", "tel:", "+1", "+44",
    )

    private val emotionWords = listOf(
        "angry", "furious", "frustrated",
        "sad", "upset", "depressed",
        "anxious", "panicked", "scared",
        "elated", "ecstatic", "thrilled",
        "hate", "love",
        "mood:",
    )

    private val highEntropyRegex = Regex("[A-Za-z0-9_\\-]{32,}")
    private val emailRegex = Regex("[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}")
    private val phoneRegex = Regex("\\+?\\d[\\d\\s().-]{7,}\\d")
    private val handleRegex = Regex("(?<![A-Za-z0-9_])@[A-Za-z0-9_]{2,}")

    /**
     * Apply the redaction rules to a single item. The output is
     * always safe to render. Items the rules decide should not be
     * displayed at all are returned with [MemoryItem.hidden] = true
     * so the caller can either skip them or surface a "hidden
     * memory" placeholder.
     */
    fun sanitize(item: MemoryItem): MemoryItem {
        val secret = looksLikeSecret(item.content) || looksLikeSecret(item.title)
        val (cleanedContent, identityStripped) = stripIdentities(item.content)
        val (cleanedTitle, titleStripped) = stripIdentities(item.title)

        val emotional = isTemporaryEmotion(item)
        val socialPattern = item.category == MemoryCategory.SOCIAL_SPEECH_PATTERN

        // Social speech patterns must never expose an identity, even
        // if the original record technically had room for it.
        val finalContent = if (socialPattern && identityStripped) cleanedContent else cleanedContent
        val finalTitle = if (socialPattern && titleStripped) cleanedTitle else cleanedTitle

        // Temporary emotions are demoted to ephemeral durability so
        // they cannot masquerade as long-term knowledge.
        val finalDurability = if (emotional) MemoryDurability.EPHEMERAL else item.durability

        return item.copy(
            content = if (secret) REDACTED else finalContent,
            title = if (secret) maskTitle(item.title) else finalTitle,
            durability = finalDurability,
            redacted = item.redacted || secret,
            hidden = item.hidden || (secret && item.category != MemoryCategory.OWNER_PREFERENCE),
        )
    }

    fun sanitizeAll(items: List<MemoryItem>): List<MemoryItem> = items.map { sanitize(it) }

    fun looksLikeSecret(text: String): Boolean {
        val lower = text.lowercase()
        if (secretKeyHints.any { lower.contains(it) }) return true
        // Long high-entropy strings without spaces look like a token.
        val match = highEntropyRegex.find(text) ?: return false
        val candidate = match.value
        val digits = candidate.count { it.isDigit() }
        val letters = candidate.count { it.isLetter() }
        return digits > 0 && letters > 0
    }

    private fun maskTitle(title: String): String =
        if (title.isBlank()) "(redacted)" else "${title.take(24)} (redacted)"

    /**
     * Returns the input with any embedded identity-like values
     * masked, plus a flag indicating whether any masking happened.
     */
    fun stripIdentities(text: String): Pair<String, Boolean> {
        if (text.isBlank()) return text to false
        var changed = false
        var out = text

        if (emailRegex.containsMatchIn(out)) {
            out = emailRegex.replace(out, "[email]")
            changed = true
        }
        if (phoneRegex.containsMatchIn(out)) {
            out = phoneRegex.replace(out, "[phone]")
            changed = true
        }
        if (handleRegex.containsMatchIn(out)) {
            out = handleRegex.replace(out, "[handle]")
            changed = true
        }

        val labelRegex = Regex("(?i)(username|user name|user_name|handle|real name|full name|name|email|phone|tel)\\s*[:=]\\s*\\S+")
        if (labelRegex.containsMatchIn(out)) {
            out = labelRegex.replace(out) { match -> "${match.groupValues[1]}: [identity]" }
            changed = true
        }
        return out to changed
    }

    /**
     * A temporary emotion is a session-scoped feeling (mood/affect
     * snapshot) that should never persist as durable memory. We
     * identify it heuristically by the durability the runtime
     * claimed plus the emotional-word vocabulary.
     */
    fun isTemporaryEmotion(item: MemoryItem): Boolean {
        val text = (item.title + " " + item.content).lowercase()
        val hasEmotionWord = emotionWords.any { text.contains(it) }
        if (!hasEmotionWord) return false
        // Only flag as temporary when the source claims long
        // durability — otherwise the runtime was already storing it
        // correctly as session/ephemeral.
        return item.durability == MemoryDurability.LONG_TERM ||
            item.durability == MemoryDurability.PERMANENT
    }
}
