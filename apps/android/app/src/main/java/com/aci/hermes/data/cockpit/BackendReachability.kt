package com.aci.hermes.data.cockpit

/**
 * Reachability of the Hermes **backend gateway** — deliberately distinct
 * from the local foreground service's running/stopped state.
 *
 * The cockpit talks to a loopback Hermes gateway (`hermes cockpit serve`).
 * Whether that gateway is *running locally* and whether it is *reachable
 * right now* are two different questions: the foreground service can be up
 * while the gateway is down, and vice-versa. Conflating them makes the app
 * imply "JARVIS is online" when only the local service is alive.
 *
 * This models the second question, derived from a short
 * [HermesCockpitClient.health] probe. The mapping is pure so it is
 * unit-tested without a socket (mirrors the [JobsSync] pattern).
 */
enum class BackendStatus {
    /** Probe in flight, or not yet run. */
    CHECKING,

    /** `/v1/health` answered 2xx — the backend is reachable. */
    CONNECTED,

    /** Transport failure (no socket, refused, timeout) — backend is down. */
    DISCONNECTED,

    /** No gateway endpoint configured at all. */
    UNPAIRED,

    /** Gateway answered, but with a non-2xx status. */
    ERROR;

    /** True only when the backend is actually reachable. */
    val isReachable: Boolean get() = this == CONNECTED

    /** True when the user should see the offline banner + retry affordance. */
    val isOffline: Boolean get() = this == DISCONNECTED || this == ERROR

    companion object {
        /**
         * Map a health-probe outcome to a status.
         *
         * [endpointConfigured] distinguishes "never set up" ([UNPAIRED])
         * from "set up but down" ([DISCONNECTED]). The health route needs
         * no token, so token pairing is irrelevant here — only whether an
         * endpoint exists matters. Never fabricates [CONNECTED]: only a
         * real 2xx maps to it.
         */
        fun from(endpointConfigured: Boolean, result: CockpitResult<*>): BackendStatus = when {
            !endpointConfigured -> UNPAIRED
            result is CockpitResult.Success<*> -> CONNECTED
            result is CockpitResult.Failure -> ERROR
            else -> DISCONNECTED // Unreachable, or any future variant — fail safe.
        }
    }
}
