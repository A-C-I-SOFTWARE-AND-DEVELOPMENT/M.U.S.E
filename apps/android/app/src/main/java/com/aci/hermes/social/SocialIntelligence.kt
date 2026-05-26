package com.aci.hermes.social

import com.aci.hermes.conversation.ConversationStore
import com.aci.hermes.conversation.ConversationTurn
import com.aci.hermes.data.memory.MemoryRepository
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.map

/**
 * Jarvis Prime Social Intelligence.
 *
 * A read-only summariser that fuses the Memory Tree with the active
 * conversation to render a one-line statement of "what Jarvis Prime
 * thinks is going on right now". Surfaced as a card on the dashboard.
 *
 * Phase 1 is intentionally lightweight: counts and a short composed
 * sentence. The richer NLP version is gated on the gateway being
 * wired so we don't ship a feature that depends on a remote runtime
 * the owner hasn't connected yet.
 */
class SocialIntelligence(
    private val memory: MemoryRepository,
    private val conversation: ConversationStore,
) {
    data class Brief(
        val knownTopics: Int,
        val pinnedTopics: Int,
        val ownerTurnsThisSession: Int,
        val lastOwnerIntent: ConversationTurn.Intent?,
        val sentence: String,
    )

    val brief: Flow<Brief> = combine(memory.tree, conversation.turns) { tree, turns ->
        val ownerTurns = turns.filter { it.author == ConversationTurn.Author.OWNER }
        val lastIntent = turns.lastOrNull { it.author == ConversationTurn.Author.JARVIS }?.intent
        Brief(
            knownTopics = tree.size,
            pinnedTopics = tree.nodes.values.count { it.pinned },
            ownerTurnsThisSession = ownerTurns.size,
            lastOwnerIntent = lastIntent,
            sentence = compose(
                knownTopics = tree.size,
                pinnedTopics = tree.nodes.values.count { it.pinned },
                ownerTurns = ownerTurns.size,
                lastIntent = lastIntent,
            ),
        )
    }.map { it }

    companion object {
        fun compose(
            knownTopics: Int,
            pinnedTopics: Int,
            ownerTurns: Int,
            lastIntent: ConversationTurn.Intent?,
        ): String {
            val intentBit = when (lastIntent) {
                ConversationTurn.Intent.EMERGENCY_STOP -> " You just engaged emergency stop."
                ConversationTurn.Intent.STATUS_QUERY -> " You're asking about runtime status."
                ConversationTurn.Intent.MEMORY_WRITE -> " You've been adding to memory."
                ConversationTurn.Intent.APPROVAL_RESPONSE -> " You're working through approvals."
                ConversationTurn.Intent.BRIEFING -> " You're briefing me on a task."
                ConversationTurn.Intent.SMALL_TALK -> " We're talking casually."
                else -> ""
            }
            val pinBit = if (pinnedTopics > 0) " $pinnedTopics pinned." else ""
            val turnBit = if (ownerTurns > 0) " ${ownerTurns} turn(s) this session." else ""
            return "Jarvis Prime knows $knownTopics topic(s).$pinBit$turnBit$intentBit".trim()
        }
    }
}
