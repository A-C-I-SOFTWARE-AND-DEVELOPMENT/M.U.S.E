package com.aci.hermes.approval.voice

import java.util.Locale

/**
 * The voice-approval ceremony — the guard that makes "approval by voice"
 * safe.
 *
 * Owner-gated actions (spend, deploy, publish, merge, credential change, …)
 * can be approved hands-free, but **never silently**. This pure state machine
 * enforces a mandatory two-step ceremony before an approval is allowed to be
 * submitted:
 *
 *   1. READING_BACK         — JARVIS speaks the exact action aloud.
 *   2. AWAITING_CONFIRMATION — the user must reply with an *explicit*
 *                              authorization phrase.
 *
 * Only an explicit affirmative (one that carries the authorization intent,
 * e.g. "yes, with authorization" / "confirm" / "approve") advances to
 * APPROVED and emits [Effect.SUBMIT_APPROVAL]. A bare "yes"/"ok"/"yeah" is
 * deliberately **insufficient** — it keeps the ceremony awaiting rather than
 * approving, so a casual acknowledgement can never push a high-risk action
 * through. Anything negative, a cancel, or a timeout abandons the ceremony.
 *
 * The coordinator never holds the owner authorization phrase. On
 * [Effect.SUBMIT_APPROVAL] the driver calls
 * [com.aci.hermes.approval.state.CockpitApprovalsRepository.approve], which
 * supplies the canonical phrase and the gateway still re-verifies it
 * server-side. This object only decides *whether the ceremony was satisfied*.
 *
 * Pure (no Android/coroutine code) so the safety behavior is exhaustively
 * unit-testable — mirroring [com.aci.hermes.voice.VoiceLoop].
 */
enum class VoiceApprovalPhase { IDLE, READING_BACK, AWAITING_CONFIRMATION, APPROVED, CANCELLED }

sealed interface VoiceApprovalEvent {
    /** Start the ceremony for a pending action, identified by [approvalId]. */
    data class Begin(val approvalId: String, val actionSummary: String) : VoiceApprovalEvent
    /** TTS finished speaking the read-back. */
    data object ReadbackSpoken : VoiceApprovalEvent
    /** The user's spoken (or typed) reply. */
    data class Phrase(val text: String) : VoiceApprovalEvent
    /** The confirmation window closed with no decision. */
    data object Timeout : VoiceApprovalEvent
    /** The user (or the system) abandoned the ceremony. */
    data object Cancel : VoiceApprovalEvent
}

class VoiceApprovalCoordinator {

    enum class Effect {
        NONE,
        /** Driver should speak [Decision.readback]. */
        SPEAK_READBACK,
        /** Ceremony satisfied — driver may call repository.approve(approvalId). */
        SUBMIT_APPROVAL,
        /** Ceremony abandoned — driver should clear/return to the queue. */
        ABANDON,
    }

    data class Decision(
        val phase: VoiceApprovalPhase,
        val effect: Effect,
        val approvalId: String,
        val readback: String,
    )

    var phase: VoiceApprovalPhase = VoiceApprovalPhase.IDLE
        private set
    private var approvalId: String = ""
    private var readback: String = ""

    fun on(event: VoiceApprovalEvent): Decision {
        val effect = when (event) {
            is VoiceApprovalEvent.Begin -> {
                approvalId = event.approvalId
                readback = buildReadback(event.actionSummary)
                phase = VoiceApprovalPhase.READING_BACK
                Effect.SPEAK_READBACK
            }

            is VoiceApprovalEvent.ReadbackSpoken -> {
                if (phase == VoiceApprovalPhase.READING_BACK) {
                    phase = VoiceApprovalPhase.AWAITING_CONFIRMATION
                }
                Effect.NONE
            }

            is VoiceApprovalEvent.Phrase -> handlePhrase(event.text)

            is VoiceApprovalEvent.Timeout,
            is VoiceApprovalEvent.Cancel -> abandon()
        }
        return Decision(phase, effect, approvalId, readback)
    }

    private fun handlePhrase(text: String): Effect {
        // A reply only counts once the action has actually been read back — you
        // cannot approve something you were never told.
        if (phase != VoiceApprovalPhase.AWAITING_CONFIRMATION) return Effect.NONE
        val normalized = normalize(text)
        return when {
            isExplicitApproval(normalized) -> {
                phase = VoiceApprovalPhase.APPROVED
                Effect.SUBMIT_APPROVAL
            }
            isNegative(normalized) -> abandon()
            // Ambiguous / bare acknowledgement: insufficient for a high-risk
            // action. Stay awaiting an explicit phrase rather than approving.
            else -> Effect.NONE
        }
    }

    private fun abandon(): Effect {
        phase = VoiceApprovalPhase.CANCELLED
        return Effect.ABANDON
    }

    private fun buildReadback(actionSummary: String): String =
        "You're about to approve: $actionSummary. " +
            "This is an owner-gated action. To authorize it, say: yes, with authorization. " +
            "Say cancel to stop."

    private fun normalize(text: String): String =
        text.lowercase(Locale.US).trim().trim('.', '!', '?', ',')

    private companion object {
        /** Explicit verbs that carry authorization intent. A bare "yes" is NOT
         *  here on purpose — it is insufficient for an owner-gated action. */
        val APPROVAL_PHRASES = listOf(
            "with authorization",
            "yes with authorization",
            "confirm",
            "approve",
            "approved",
            "i approve",
            "i authorize",
            "authorize it",
            "authorize",
        )
        val NEGATIVE_PHRASES = listOf(
            "no", "nope", "cancel", "stop", "abort", "don't", "do not",
            "never mind", "nevermind", "reject", "deny",
        )

        fun matches(text: String, phrases: List<String>): Boolean =
            phrases.any { text == it || text.startsWith("$it ") || text.contains(" $it") }
    }

    private fun isExplicitApproval(text: String): Boolean {
        if (text.isBlank()) return false
        // Accept the strong owner ceremony anywhere in the phrase…
        if (text.contains("with authorization")) return true
        return matches(text, APPROVAL_PHRASES)
    }

    private fun isNegative(text: String): Boolean = matches(text, NEGATIVE_PHRASES)
}
