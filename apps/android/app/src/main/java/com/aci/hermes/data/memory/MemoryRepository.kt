package com.aci.hermes.data.memory

import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

/**
 * In-memory store of [MemoryItem]s with mock seed data. Real
 * gateway/runtime syncing slots in later — until then this stand-in
 * is sufficient for the Memory transparency screen to exercise the
 * full UI flow end-to-end.
 *
 * All reads pass through [MemoryRedactor] so the UI never sees a
 * secret value or an identity that should have been abstracted away.
 *
 * Owner actions (correct, delete, hide, reveal) push [MemoryAction]
 * events onto [actions]; the runtime bridge subscribes to that flow
 * and forwards the event to the gateway when one is configured.
 */
class MemoryRepository(
    seed: List<MemoryItem> = MockMemorySeed.items,
) {
    private val mutex = Mutex()

    private val _items: MutableStateFlow<List<MemoryItem>> =
        MutableStateFlow(seed)

    /** Raw items, with [MemoryRedactor] applied. Suitable for display. */
    val items: StateFlow<List<MemoryItem>> = _items.asStateFlow()

    private val _actions = MutableSharedFlow<MemoryAction>(
        replay = 0,
        extraBufferCapacity = 32,
    )
    val actions: SharedFlow<MemoryAction> = _actions.asSharedFlow()

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
