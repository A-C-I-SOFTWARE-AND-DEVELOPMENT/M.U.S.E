package com.aci.hermes.notify

import com.aci.hermes.ui.navigation.Screen

/**
 * Maps a [WorkEvent] to the in-app destination its notification should open,
 * and defines the intent-extra contract the [JarvisNotifier] → `MainActivity`
 * → `HermesNavHost` chain uses to honour the tap.
 *
 * Destinations are the *existing* routes ([Screen]); this adds no new screens.
 *  - approvals / blocked → **Approvals** (the actionable owner queue)
 *  - job lifecycle (started/completed/research/tests) → **Tasks** (the live
 *    work list). Cockpit jobs have no dedicated detail screen yet, so the
 *    list is the closest populated surface — see MOBILE-NOTIFY-004.
 *  - failures / worker attention / emergency → **Diagnostics** (the
 *    error/health surface).
 */
object DeepLink {

    /** Intent extra carrying a nav route the activity should open on tap. */
    const val EXTRA_NAV_ROUTE = "jarvis_nav_route"

    fun routeFor(event: WorkEvent): String = when (event) {
        is WorkEvent.ApprovalRequired,
        is WorkEvent.JobBlocked,
        -> Screen.Approvals.route

        is WorkEvent.JobStarted,
        is WorkEvent.JobCompleted,
        is WorkEvent.ResearchComplete,
        is WorkEvent.TestsFailed,
        -> Screen.Tasks.route

        is WorkEvent.JobFailed,
        is WorkEvent.WorkerNeedsAttention,
        is WorkEvent.EmergencyStopTriggered,
        -> Screen.Diagnostics.route
    }
}
