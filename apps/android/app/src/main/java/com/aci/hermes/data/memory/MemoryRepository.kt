package com.aci.hermes.data.memory

import com.aci.hermes.data.cockpit.CockpitResult
import com.aci.hermes.data.cockpit.HermesCockpitClient
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

/** Sync state of the memory store against the cockpit gateway. */
sealed interface MemorySync {
    /** Not yet refreshed. */
    data object Idle : MemorySync
    /** A gateway fetch is in flight. */
    data object Loading : MemorySync
    /** No gateway paired — items are the local/preview seed, not live. */
    data object MockOnly : MemorySync
    /** Live items loaded from the gateway (`count` real records). */
    data class Loaded(val count: Int) : MemorySync
    /** Paired but the gateway couldn't serve the request — honest, no fake data. */
    data class Error(val message: String) : MemorySync
}

/**
 * Store of [MemoryItem]s backed by the cockpit gateway when paired.
 *
 * - **Paired** (a [client] + [paired]==true): [refresh] pulls the real
 *   JARVIS memory via `GET /v1/cockpit/memory` and maps it to the domain
 *   model; [delete] removes it on the gateway. No mock data is shown.
 * - **Unpaired / preview / tests**: falls back to the [seed] (mock) so the
 *   screen renders without a daemon. Production wires an **empty** seed +
 *   a client, so nothing fake reaches a paired user.
 *
 * All reads pass through [MemoryRedactor]. Owner actions push
 * [MemoryAction] events onto [actions]. `correct`/`hide`/`reveal` remain
 * local-optimistic — the gateway has no update/hide endpoint yet (the
 * cockpit memory API today is list/create/delete); they are documented
 * as such rather than silently faked.
 */
class MemoryRepository(
    seed: List<MemoryItem> = MockMemorySeed.items,
    private val client: HermesCockpitClient? = null,
    private val paired: () -> Boolean = { false },
) {
    private val mutex = Mutex()

    private val _items: MutableStateFlow<List<MemoryItem>> =
        MutableStateFlow(seed)

    /** Raw items, with [MemoryRedactor] applied. Suitable for display. */
    val items: StateFlow<List<MemoryItem>> = _items.asStateFlow()

    private val _sync: MutableStateFlow<MemorySync> = MutableStateFlow(MemorySync.Idle)
    val sync: StateFlow<MemorySync> = _sync.asStateFlow()

    /** True when reads/writes go to a real paired gateway. */
    val isLive: Boolean get() = client != null && paired()

    private val _actions = MutableSharedFlow<MemoryAction>(
        replay = 0,
        extraBufferCapacity = 32,
    )
    val actions: SharedFlow<MemoryAction> = _actions.asSharedFlow()

    /**
     * Pull the live memory list from the gateway when paired. On a paired
     * gateway error the items are left as-is and [sync] carries the error
     * — never replaced with stub data.
     */
    suspend fun refresh() {
        val c = client
        if (c == null || !paired()) {
            _sync.value = MemorySync.MockOnly
            return
        }
        _sync.value = MemorySync.Loading
        when (val res = c.memoryList()) {
            is CockpitResult.Success -> {
                val mapped = res.value.items.map { it.toDomain() }
                _items.value = mapped
                _sync.value = MemorySync.Loaded(mapped.size)
            }
            is CockpitResult.Failure ->
                _sync.value = MemorySync.Error(
                    "Gateway error ${res.httpStatus}: ${res.error.message}"
                )
            is CockpitResult.Unreachable ->
                _sync.value = MemorySync.Error(res.message)
        }
    }

    /** Sanitized list ready for the UI. Pure function over [items]. */
    fun visible(): List<MemoryItem> = MemoryRedactor.sanitizeAll(_items.value)
        .filterNot { it.hidden }

    fun byId(id: String): MemoryItem? = visible().firstOrNull { it.id == id }

    suspend fun correct(id: String, newContent: String, reason: String?) {
        mutex.withLock {
            val existing = _items.value.firstOrNull { it.id == id } ?: return@withLock
            val updated = existing.copy(
                content = newContent,
                updatedAt = System.currentTimeMillis(),
                confidence = MemoryConfidence.CONFIRMED,
            )
            _items.update { list -> list.map { if (it.id == id) updated else it } }
            _actions.tryEmit(
                MemoryAction.Correct(
                    itemId = id,
                    previousContent = existing.content,
                    newContent = newContent,
                    reason = reason,
                )
            )
        }
    }

    suspend fun delete(id: String, reason: String?) {
        mutex.withLock {
            if (_items.value.none { it.id == id }) return@withLock
            val c = client
            if (c != null && paired()) {
                // Real delete on the gateway; only mirror locally on success.
                when (c.memoryDelete(id)) {
                    is CockpitResult.Success -> Unit
                    is CockpitResult.Failure ->
                        return@withLock run { _sync.value = MemorySync.Error("Delete rejected by gateway") }
                    is CockpitResult.Unreachable ->
                        return@withLock run { _sync.value = MemorySync.Error("Couldn't reach the gateway to delete") }
                }
            }
            _items.update { list -> list.filterNot { it.id == id } }
            _actions.tryEmit(MemoryAction.Delete(itemId = id, reason = reason))
        }
    }

    suspend fun hide(id: String) {
        mutex.withLock {
            _items.update { list -> list.map { if (it.id == id) it.copy(hidden = true) else it } }
            _actions.tryEmit(MemoryAction.Hide(itemId = id))
        }
    }

    suspend fun reveal(id: String) {
        mutex.withLock {
            _items.update { list -> list.map { if (it.id == id) it.copy(hidden = false) else it } }
            _actions.tryEmit(MemoryAction.Reveal(itemId = id))
        }
    }
}

/**
 * Seed data the Memory screen renders while the gateway sync isn't
 * wired. Crafted to exercise every redaction rule (a fake secret,
 * an identity-leaking social pattern, a "temporary emotion" stored
 * with an inflated durability) so the privacy filter has something
 * to catch in development.
 */
object MockMemorySeed {

    private const val DAY = 86_400_000L
    private val now = System.currentTimeMillis()

    val items: List<MemoryItem> = listOf(
        MemoryItem(
            id = "pref-stack",
            category = MemoryCategory.OWNER_PREFERENCE,
            title = "Preferred Android build",
            content = "Owner prefers Material 3, single-Activity Compose with hand-rolled DI.",
            durability = MemoryDurability.LONG_TERM,
            confidence = MemoryConfidence.HIGH,
            provenance = MemoryProvenance(source = "operator-mode", recordedAt = now - 30 * DAY),
            createdAt = now - 30 * DAY,
            updatedAt = now - 2 * DAY,
            tags = listOf("android", "stack"),
        ),
        MemoryItem(
            id = "pref-tone",
            category = MemoryCategory.OWNER_PREFERENCE,
            title = "Voice and tone",
            content = "Direct, plain English. Cut filler. Push back on weak ideas.",
            durability = MemoryDurability.PERMANENT,
            confidence = MemoryConfidence.CONFIRMED,
            provenance = MemoryProvenance(source = "companion-mode", recordedAt = now - 60 * DAY),
            createdAt = now - 60 * DAY,
        ),
        MemoryItem(
            id = "proj-hermes-orch",
            category = MemoryCategory.PROJECT_MEMORY,
            title = "Hermes orchestration primitives",
            content = "Five primitives only: Job, Worker profile, Model routing, Validation gate, Decision ledger. Don't invent a sixth.",
            durability = MemoryDurability.LONG_TERM,
            confidence = MemoryConfidence.HIGH,
            provenance = MemoryProvenance(source = "docs/orchestration/README.md", recordedAt = now - 14 * DAY),
            createdAt = now - 14 * DAY,
            tags = listOf("orchestration", "hermes"),
        ),
        MemoryItem(
            id = "lesson-tests-near",
            category = MemoryCategory.WORKFLOW_LESSON,
            title = "Tests live next to code",
            content = "Mirror src layout under tests/. Don't add test files at the repo root.",
            durability = MemoryDurability.LONG_TERM,
            confidence = MemoryConfidence.HIGH,
            provenance = MemoryProvenance(source = "CLAUDE.md", recordedAt = now - 21 * DAY),
            createdAt = now - 21 * DAY,
        ),
        MemoryItem(
            id = "task-cur-memory-ui",
            category = MemoryCategory.TASK_CONTEXT,
            title = "Memory transparency UI in progress",
            content = "Building MemoryScreen with category filter, search, correct/delete dialogs.",
            durability = MemoryDurability.SHORT_TERM,
            confidence = MemoryConfidence.HIGH,
            provenance = MemoryProvenance(source = "session-current", recordedAt = now - 60_000),
            createdAt = now - 60_000,
            tags = listOf("ui", "memory"),
        ),
        MemoryItem(
            id = "decision-no-hilt",
            category = MemoryCategory.DECISION_RECORD,
            title = "No Hilt in Android app",
            content = "Dependency graph is small enough that Hilt's indirection costs more than the wiring. Use hand-rolled AppContainer.",
            durability = MemoryDurability.PERMANENT,
            confidence = MemoryConfidence.CONFIRMED,
            provenance = MemoryProvenance(source = "apps/android/docs/ARCHITECTURE.md", recordedAt = now - 90 * DAY),
            createdAt = now - 90 * DAY,
        ),
        // Social speech pattern — content intentionally includes
        // an identity to verify the redactor strips it.
        MemoryItem(
            id = "social-greeting",
            category = MemoryCategory.SOCIAL_SPEECH_PATTERN,
            title = "Morning greeting pattern",
            content = "username: jdoe — Owner opens the day with a short status sentence, not a salutation.",
            durability = MemoryDurability.LONG_TERM,
            confidence = MemoryConfidence.MEDIUM,
            provenance = MemoryProvenance(source = "companion-mode", recordedAt = now - 7 * DAY),
            createdAt = now - 7 * DAY,
        ),
        MemoryItem(
            id = "session-current",
            category = MemoryCategory.SESSION_MEMORY,
            title = "Current focus",
            content = "Owner is shipping the Memory transparency screen this session.",
            durability = MemoryDurability.SESSION,
            confidence = MemoryConfidence.HIGH,
            provenance = MemoryProvenance(source = "session-current", recordedAt = now - 5 * 60_000),
            createdAt = now - 5 * 60_000,
        ),
        // Looks like a secret on purpose — must be redacted in UI.
        MemoryItem(
            id = "leaked-token",
            category = MemoryCategory.TASK_CONTEXT,
            title = "Gateway api_key",
            content = "api_key=sk-AbCdEfGhIjKlMnOpQrStUvWxYz0123456789",
            durability = MemoryDurability.SHORT_TERM,
            confidence = MemoryConfidence.LOW,
            provenance = MemoryProvenance(source = "session-current", recordedAt = now - 10 * 60_000),
            createdAt = now - 10 * 60_000,
        ),
        // Temporary emotion mis-stored as long-term — redactor must
        // demote it to ephemeral.
        MemoryItem(
            id = "mood-spike",
            category = MemoryCategory.SESSION_MEMORY,
            title = "Mood: frustrated with merge conflicts",
            content = "Owner was frustrated by repeated merge conflicts in the gateway plugin tree.",
            durability = MemoryDurability.LONG_TERM,
            confidence = MemoryConfidence.LOW,
            provenance = MemoryProvenance(source = "session-current", recordedAt = now - 30 * 60_000),
            createdAt = now - 30 * 60_000,
        ),
    )
}
