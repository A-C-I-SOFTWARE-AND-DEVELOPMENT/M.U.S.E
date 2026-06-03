package com.aci.hermes.ui.screens.jobs

import kotlin.math.min

/**
 * Pure cadence policy for the Jobs poller — extracted so the lifecycle-aware
 * back-off is unit-testable without a coroutine or a clock.
 *
 * Rules (owner's spec): poll fast while a job is active **and** the screen is
 * visible; slower when active but backgrounded; slower still when idle but
 * visible; **stop** when there are no active jobs and the screen is hidden (no
 * permanent always-on poller). Transport errors back off exponentially up to a
 * cap rather than hammering an unreachable gateway.
 */
object JobsPolling {
    const val FAST_MS = 4_000L
    const val SLOW_MS = 20_000L
    const val MAX_BACKOFF_MS = 60_000L
    const val STOP = -1L
    const val IDLE_CYCLES_BEFORE_STOP = 3

    fun nextDelayMs(
        hasActive: Boolean,
        visible: Boolean,
        consecutiveErrors: Int,
        idleCycles: Int,
    ): Long {
        // No active work and the screen is hidden → stop entirely after a grace
        // window. The next foreground/visibility event restarts the poller.
        if (!visible && !hasActive && idleCycles >= IDLE_CYCLES_BEFORE_STOP) return STOP
        if (consecutiveErrors > 0) {
            val factor = 1L shl min(consecutiveErrors - 1, 4) // 1,2,4,8,16
            return min(FAST_MS * factor, MAX_BACKOFF_MS)
        }
        if (hasActive) return if (visible) FAST_MS else SLOW_MS
        return SLOW_MS
    }
}
