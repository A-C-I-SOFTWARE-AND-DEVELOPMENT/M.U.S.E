package com.aci.hermes.ui.screens.home

import com.aci.hermes.data.jarvis.ApprovalRisk
import com.aci.hermes.data.jarvis.JarvisHomeState
import com.aci.hermes.data.jarvis.JarvisPresence

/**
 * The Jarvis Prime cockpit invariant: the emergency stop is *always*
 * visible on Home, especially when a serious or critical approval is
 * pending. This object encodes that rule in one place so the Compose
 * screen reads from it and a JVM test pins it.
 *
 * Owner-control language for the confirm dialog also lives here.
 */
object HomeEmergencyStopGuard {

    /**
     * Returns true iff the home screen must render the emergency-stop
     * button right now. The current rule is unconditional — the stop
     * is the owner's last-line control and must never be hidden. This
     * is enforced as a function so a future change can be tightened
     * (never loosened) here and the test will catch any regression.
     */
    fun shouldShowEmergencyStop(state: JarvisHomeState): Boolean {
        // Belt-and-braces: never hide for serious/critical contexts.
        if (state.hasCriticalApproval || state.hasSeriousApproval) return true
        if (state.presence == JarvisPresence.CRITICAL_ACTION_PENDING) return true
        if (state.presence == JarvisPresence.SERIOUS_ACTION_PENDING) return true
        // Always show in every other state too.
        return true
    }

    /**
     * True when the home surface is "quiet" — no active task, no
     * pending approval, no suggested next action. The screen uses
     * this to render an empty-state hint so the cockpit doesn't
     * look broken when Jarvis has nothing to do.
     */
    fun isQuietDay(state: JarvisHomeState): Boolean =
        state.activeTask == null &&
            state.pendingApprovals.isEmpty() &&
            state.suggestedNextAction == null

    /**
     * Owner-control language for the emergency-stop confirm dialog.
     * Co-located with the visibility rule so both the test and the
     * screen reference the same string.
     */
    const val EMERGENCY_STOP_CONFIRM_TITLE = "Engage emergency stop?"
    const val EMERGENCY_STOP_CONFIRM_BODY =
        "Owner action: halts HermesService immediately and blocks ask, voice, " +
            "and worker actions until you deactivate. Pending tasks stay saved."
    const val EMERGENCY_STOP_CONFIRM_BUTTON = "Engage"

    /**
     * Copy for the "quiet day" hint shown when there's no active
     * task, no pending approval, and no suggested action.
     */
    const val QUIET_DAY_HINT =
        "Jarvis is on standby. Ask anything, or tap the icon to start a chat. " +
            "Emergency stop stays available below."

    /**
     * Approval-risk → presence mapping kept as a property so the
     * pinning test asserts the contract.
     */
    fun expectedPresenceFor(risk: ApprovalRisk): JarvisPresence = when (risk) {
        ApprovalRisk.LOW -> JarvisPresence.WAITING_FOR_APPROVAL
        ApprovalRisk.SERIOUS -> JarvisPresence.SERIOUS_ACTION_PENDING
        ApprovalRisk.CRITICAL -> JarvisPresence.CRITICAL_ACTION_PENDING
    }
}
