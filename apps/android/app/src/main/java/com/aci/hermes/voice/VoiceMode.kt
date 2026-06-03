package com.aci.hermes.voice

/**
 * The voice interaction modes the cockpit exposes. The first three map
 * directly onto the canonical backend mode contract
 * (`hermes_cli.voice_models`: ``push_to_talk`` / ``wake_word`` /
 * ``driving_capture``); [CODING_DICTATION] and [VOICE_APPROVAL] are UX modes
 * layered on top of the same pipeline (they still send transcripts through the
 * backend, which owns classification + the safety veto).
 *
 * [backendMode] is the string the gateway voice endpoints expect, so the
 * client never invents a mode name the backend doesn't recognise (and the
 * backend normalises anything unknown to ``push_to_talk`` regardless).
 */
enum class VoiceMode(val backendMode: String) {
    /** Default. The user is the trigger: tap/hold to capture. Safe everywhere. */
    PUSH_TO_TALK("push_to_talk"),

    /** Hands-free Presence Mode: a wake word / attention starts the turn. */
    HANDS_FREE("wake_word"),

    /** Mounted-in-a-vehicle capture: mandatory read-back, short-form speech,
     *  high-risk actions auto-deferred, publish vetoed. */
    DRIVING_SAFE("driving_capture"),

    /** Verbatim dictation into chat/editor — captured as text, never run as a
     *  command. Routed as a plain push-to-talk transcript. */
    CODING_DICTATION("push_to_talk"),

    /** Approve a pending owner-gated action by voice, gated by the
     *  read-back + explicit-confirmation ceremony
     *  ([com.aci.hermes.approval.voice.VoiceApprovalCoordinator]). */
    VOICE_APPROVAL("push_to_talk");

    companion object {
        val DEFAULT = PUSH_TO_TALK
    }
}
