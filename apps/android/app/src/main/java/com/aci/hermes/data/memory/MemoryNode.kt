package com.aci.hermes.data.memory

import kotlinx.serialization.Serializable
import java.util.UUID

/**
 * A single node in the Jarvis Prime Memory Tree.
 *
 * Nodes form a tree (one parent, many children). Each node carries a
 * topic, optional body, and free-form tags. The tree is intended to be
 * the user-facing surface of what Jarvis Prime remembers about the
 * owner and their work — never opaque, never hidden, always editable.
 *
 * The data class is `Serializable` so the [MemoryRepository] can
 * round-trip the whole tree through DataStore JSON. `id` is stable and
 * generated client-side; equality is value-based.
 */
@Serializable
data class MemoryNode(
    val id: String = UUID.randomUUID().toString(),
    val parentId: String? = null,
    val topic: String,
    val body: String = "",
    val tags: List<String> = emptyList(),
    val pinned: Boolean = false,
    val createdAt: Long = System.currentTimeMillis(),
    val updatedAt: Long = System.currentTimeMillis(),
    /**
     * Where this memory came from. Surfaced in the UI so the owner can
     * trace any claim Jarvis Prime makes back to its origin.
     */
    val provenance: Provenance = Provenance.MANUAL,
) {
    @Serializable
    enum class Provenance {
        MANUAL,         // owner typed it in directly
        CONVERSATION,   // captured from a conversation turn
        APPROVAL,       // captured from an approval decision
        GATEWAY_EVENT,  // captured from a worker / gateway event
        INFERRED,       // derived by Jarvis Prime — needs owner review
    }
}
