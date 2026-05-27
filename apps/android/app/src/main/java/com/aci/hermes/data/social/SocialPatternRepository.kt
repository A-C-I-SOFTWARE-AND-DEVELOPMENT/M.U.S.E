package com.aci.hermes.data.social

import android.content.Context
import com.aci.hermes.data.model.SocialPattern
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import java.io.File

/**
 * Persists Jarvis Prime [SocialPattern]s. Mirrors the
 * file-backed approach used by HermesTaskRepository: small dataset,
 * private filesDir, atomic temp-file rename.
 *
 * Every write path runs through [PrivacyRedactor.sanitize] so that
 * identity tokens never make it to disk.
 */
class SocialPatternRepository(
    private val dir: File,
) {
    constructor(context: Context) : this(context.filesDir)

    private val file = File(dir, FILE_NAME)
    private val mutex = Mutex()
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    private val _patterns = MutableStateFlow<List<SocialPattern>>(emptyList())
    val patterns: StateFlow<List<SocialPattern>> = _patterns.asStateFlow()

    init {
        scope.launch { loadFromDisk() }
    }

    /** Insert or update [pattern]. Identity is redacted before storage. */
    suspend fun upsert(pattern: SocialPattern): SocialPattern = mutex.withLock {
        val sanitized = PrivacyRedactor.sanitize(pattern)
        val existing = _patterns.value
        val idx = existing.indexOfFirst { it.id == sanitized.id }
        val next = if (idx >= 0) {
            existing.toMutableList().also { it[idx] = sanitized }
        } else {
            listOf(sanitized) + existing
        }
        _patterns.value = next
        writeToDisk(next)
        sanitized
    }

    /** Drop a pattern entirely. */
    suspend fun delete(id: String) = mutex.withLock {
        val next = _patterns.value.filterNot { it.id == id }
        _patterns.value = next
        writeToDisk(next)
    }

    /** Drop everything. Used by the Settings "reset all" action. */
    suspend fun deleteAll() = mutex.withLock {
        _patterns.value = emptyList()
        writeToDisk(emptyList())
    }

    /**
     * Replace a pattern's user-editable fields. The new copy keeps
     * the same id, records the previous id in [SocialPattern.correctedFrom],
     * and is sanitized like any other write.
     */
    suspend fun correct(
        id: String,
        title: String,
        summary: String,
        safeUsage: String,
        unsafeUsage: String,
    ): SocialPattern? = mutex.withLock {
        val existing = _patterns.value
        val idx = existing.indexOfFirst { it.id == id }
        if (idx < 0) return@withLock null
        val previous = existing[idx]
        val replacement = previous.copy(
            title = title,
            summary = summary,
            safeUsage = safeUsage,
            unsafeUsage = unsafeUsage,
            correctedFrom = previous.correctedFrom ?: previous.id,
            updatedAt = System.currentTimeMillis(),
        )
        val sanitized = PrivacyRedactor.sanitize(replacement)
        val next = existing.toMutableList().also { it[idx] = sanitized }
        _patterns.value = next
        writeToDisk(next)
        sanitized
    }

    fun byId(id: String): SocialPattern? = _patterns.value.firstOrNull { it.id == id }

    private suspend fun loadFromDisk() = withContext(Dispatchers.IO) {
        if (!file.exists()) return@withContext
        runCatching {
            val text = file.readText()
            if (text.isBlank()) return@runCatching
            val envelope = json.decodeFromString(Envelope.serializer(), text)
            // Re-sanitize on read so older entries benefit from any
            // tightening of the redaction rules.
            _patterns.value = envelope.patterns.map(PrivacyRedactor::sanitize)
        }
    }

    private suspend fun writeToDisk(list: List<SocialPattern>) = withContext(Dispatchers.IO) {
        runCatching {
            val envelope = Envelope(version = 1, patterns = list)
            val text = json.encodeToString(Envelope.serializer(), envelope)
            val tmp = File(file.parentFile, "$FILE_NAME.tmp")
            tmp.writeText(text)
            if (!tmp.renameTo(file)) {
                file.writeText(text)
                tmp.delete()
            }
        }
    }

    @Serializable
    private data class Envelope(val version: Int = 1, val patterns: List<SocialPattern> = emptyList())

    companion object {
        private const val FILE_NAME = "jarvis_social_patterns.json"
        private val json = Json {
            ignoreUnknownKeys = true
            encodeDefaults = true
            prettyPrint = false
        }
    }
}
