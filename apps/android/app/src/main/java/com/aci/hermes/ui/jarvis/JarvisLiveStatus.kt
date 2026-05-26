package com.aci.hermes.ui.jarvis

/**
 * Output of [JarvisLiveStatusProjector] — the single bundle of UI fields
 * that JarvisLiveScreen renders. Every projection produces non-blank
 * [statusPillText] and [statusLine] so the user always has language for
 * what Jarvis is doing.
 */
data class JarvisLiveStatus(
    val iconState: IconState,
    val avatarActivity: JarvisAvatarActivity,
    val statusPillText: String,
    val statusLine: String,
    val detailLine: String?,
    val progressLabel: String?,
    val shouldPulse: Boolean,
    val shouldShowApprovalButton: Boolean,
    val shouldShowEmergencyButton: Boolean,
)

/**
 * Visible activity overlay applied on top of the base
 * [JarvisPrimeIcon] by [JarvisLivingAvatar].
 *
 *  - [Static] suppresses every motion overlay; used by reduced-motion
 *    paths and unrecoverable states (offline, blocked).
 *  - [Subtle] adds nothing extra — the base icon's own breath is the
 *    motion.
 *  - [AnimatedDots] / [ScanRing] / [TaskOrbit] / [CheckPulse] /
 *    [MouthPulse] are task-aware indicators.
 *  - [GoldRing] and [CrimsonLockedRing] are attention rings drawn
 *    around the icon even in reduced-motion mode (they are static
 *    rings when motion is disabled).
 */
enum class JarvisAvatarActivity {
    Static,
    Subtle,
    AnimatedDots,
    ScanRing,
    TaskOrbit,
    CheckPulse,
    MouthPulse,
    GoldRing,
    CrimsonLockedRing,
}

/**
 * Phase of a long-running background task. Producers (the
 * orchestrator, individual workers) decide which phase they are in;
 * the projector decides the matching status line and avatar activity.
 */
enum class JarvisWorkerPhase {
    NONE,
    PLANNING,
    CODING,
    TESTING,
    REVIEWING,
}

/**
 * Chat streaming pipeline state. Surfaced separately from
 * [IconState] so the projector can distinguish "thinking" (model
 * reasoning, no audio) from "speaking" (TTS playing) during a single
 * chat turn.
 */
enum class JarvisChatStreamState {
    IDLE,
    THINKING,
    SPEAKING,
}
