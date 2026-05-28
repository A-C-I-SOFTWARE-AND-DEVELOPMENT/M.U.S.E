package com.aci.hermes.data.life

import kotlin.time.Duration
import kotlin.time.Duration.Companion.minutes
import kotlin.time.Duration.Companion.seconds

/**
 * Decides which ambient [AvatarBehavior] the idle avatar should be in,
 * given how long it's been idle, the time of day, and whether a
 * recommendation is waiting. Pure and deterministic so the "Jarvis
 * sleeps at night / wanders when bored / leans in to suggest things"
 * behavior is fully unit-testable — no clock, no Android.
 *
 * The caller (the overlay service) feeds it a [Tick] on a timer and
 * renders whatever behavior comes back.
 */
class BehaviorScheduler(private val config: Config = Config()) {

    data class Config(
        /** Local hour (inclusive) the sleep window opens. */
        val sleepStartHour: Int = 23,
        /** Local hour (exclusive) the sleep window closes. */
        val sleepEndHour: Int = 6,
        /** Idle this long → drift from IDLE into WANDER. */
        val wanderAfter: Duration = 45.seconds,
        /** Idle this long → fall asleep regardless of the clock. */
        val deepSleepAfter: Duration = 12.minutes,
        /** Minimum spacing between unsolicited recommendations. */
        val recommendCooldown: Duration = 8.minutes,
    )

    data class Tick(
        /** How long the user has been away from the avatar. */
        val idleFor: Duration,
        /** Local hour, 0..23. */
        val localHour: Int,
        /** A recommendation is queued and ready to surface. */
        val hasPendingRecommendation: Boolean,
        /** Time since the last recommendation was shown. */
        val sinceLastRecommendation: Duration,
        /** True while the agent is actively working — suppresses ambient life. */
        val agentBusy: Boolean,
        /** User has muted ambient motion (reduced-motion / focus mode). */
        val ambientMuted: Boolean = false,
    )

    fun decide(tick: Tick): AvatarBehavior {
        // Agent work and explicit mute win — the body holds still.
        if (tick.agentBusy || tick.ambientMuted) return AvatarBehavior.IDLE

        // A ready recommendation interrupts everything except sleep-by-clock,
        // and only after the cooldown so Jarvis isn't naggy.
        val mayRecommend = tick.hasPendingRecommendation &&
            tick.sinceLastRecommendation >= config.recommendCooldown
        if (mayRecommend && !inSleepWindow(tick.localHour)) {
            return AvatarBehavior.RECOMMEND
        }

        if (shouldSleep(tick)) return AvatarBehavior.SLEEP

        return when {
            tick.idleFor >= config.wanderAfter -> AvatarBehavior.WANDER
            else -> AvatarBehavior.IDLE
        }
    }

    private fun shouldSleep(tick: Tick): Boolean =
        inSleepWindow(tick.localHour) || tick.idleFor >= config.deepSleepAfter

    /** Handles windows that wrap past midnight (e.g. 23 → 6). */
    private fun inSleepWindow(hour: Int): Boolean {
        val start = config.sleepStartHour
        val end = config.sleepEndHour
        return if (start <= end) hour in start until end else hour >= start || hour < end
    }
}
