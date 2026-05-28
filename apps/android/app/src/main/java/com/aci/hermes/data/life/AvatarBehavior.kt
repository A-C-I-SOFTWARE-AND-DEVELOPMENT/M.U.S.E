package com.aci.hermes.data.life

/**
 * What the avatar is *doing with its body* when it isn't mid-task. This
 * is the "feels alive" layer: idle fidgets, wandering, sleeping at
 * night, and offering recommendations. It is orthogonal to the agent
 * work state ([com.aci.hermes.ui.screens.live.JarvisLiveState]) — the
 * renderer blends the two (e.g. "working + ambientWander").
 */
enum class AvatarBehavior {
    /** Default resting fidget — breathing, occasional look-around. */
    IDLE,

    /** Strolls across the overlay between idle spots. */
    WANDER,

    /** Curled up / dimmed during the sleep window or deep inactivity. */
    SLEEP,

    /** Waking transition out of SLEEP. */
    WAKE,

    /** Doing a small ambient chore (tidying its corner, stretching). */
    AMBIENT_TASK,

    /** Leaning in to offer a proactive recommendation. */
    RECOMMEND,
}
