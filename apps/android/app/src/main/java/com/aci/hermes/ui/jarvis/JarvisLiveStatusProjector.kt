package com.aci.hermes.ui.jarvis

/**
 * Snapshot of every signal the live screen needs in order to decide
 * what to show. All fields default to safe values so a caller that
 * only has [iconState] can still project a meaningful status.
 *
 * The projector is intentionally a pure function over this snapshot
 * — no Android dependencies — so it tests under stock JVM JUnit and
 * the same logic powers both the in-app screen and (later) the
 * floating-bubble overlay.
 */
data class JarvisLiveInputs(
    val iconState: IconState,
    val currentRoute: String? = null,
    val activeTaskTitle: String? = null,
    val activeTaskStepLabel: String? = null,
    val activeTaskStepIndex: Int? = null,
    val activeTaskStepTotal: Int? = null,
    val workerPhase: JarvisWorkerPhase = JarvisWorkerPhase.NONE,
    val chatStream: JarvisChatStreamState = JarvisChatStreamState.IDLE,
    val approvalQueueCount: Int = 0,
    val emergencyStopActive: Boolean = false,
    val gatewayOnline: Boolean = true,
    val reducedMotion: Boolean = false,
)

/**
 * Collapses [JarvisLiveInputs] into a single [JarvisLiveStatus].
 *
 * Resolution order (top wins):
 *  1. emergency stop
 *  2. gateway offline
 *  3. critical / serious action pending
 *  4. blocked
 *  5. approval queue
 *  6. speaking
 *  7. listening
 *  8. thinking
 *  9. working (split by [JarvisWorkerPhase])
 * 10. complete (transient flash)
 * 11. warning
 * 12. idle (floor)
 *
 * Every code path produces non-blank [JarvisLiveStatus.statusPillText]
 * and [JarvisLiveStatus.statusLine]; tests pin this so a future state
 * cannot accidentally render blank UI.
 */
object JarvisLiveStatusProjector {

    fun project(inputs: JarvisLiveInputs): JarvisLiveStatus {
        val progress = buildProgressLabel(inputs)
        val detail = inputs.activeTaskTitle?.takeIf { it.isNotBlank() }

        // 1. Emergency stop — outranks every other signal.
        if (inputs.emergencyStopActive) {
            return base(
                iconState = inputs.iconState,
                activity = JarvisAvatarActivity.CrimsonLockedRing,
                pill = "EMERGENCY STOP",
                line = "Emergency stop active.",
                detail = detail,
                progress = null,
                pulse = false,
                approval = false,
                emergency = true,
                reducedMotion = inputs.reducedMotion,
            )
        }

        // 2. Gateway offline — never claim activity we cannot perform.
        if (!inputs.gatewayOnline) {
            return base(
                iconState = IconState.OFFLINE,
                activity = JarvisAvatarActivity.Static,
                pill = "Offline",
                line = "Gateway offline.",
                detail = detail,
                progress = null,
                pulse = false,
                approval = false,
                emergency = false,
                reducedMotion = inputs.reducedMotion,
            )
        }

        // 3. Critical / serious approvals.
        if (inputs.iconState == IconState.CRITICAL_ACTION_PENDING) {
            return base(
                iconState = inputs.iconState,
                activity = JarvisAvatarActivity.CrimsonLockedRing,
                pill = "Critical approval",
                line = "Critical action — needs your approval.",
                detail = detail,
                progress = null,
                pulse = true,
                approval = true,
                emergency = false,
                reducedMotion = inputs.reducedMotion,
            )
        }
        if (inputs.iconState == IconState.SERIOUS_ACTION_PENDING) {
            return base(
                iconState = inputs.iconState,
                activity = JarvisAvatarActivity.GoldRing,
                pill = "Approval needed",
                line = "Serious action — needs your approval.",
                detail = detail,
                progress = null,
                pulse = true,
                approval = true,
                emergency = false,
                reducedMotion = inputs.reducedMotion,
            )
        }

        // 4. Blocked.
        if (inputs.iconState == IconState.BLOCKED) {
            return base(
                iconState = inputs.iconState,
                activity = JarvisAvatarActivity.Static,
                pill = "Blocked",
                line = "Blocked — action needed.",
                detail = detail,
                progress = null,
                pulse = false,
                approval = false,
                emergency = false,
                reducedMotion = inputs.reducedMotion,
            )
        }

        // 5. Approval queue (basic pending approval).
        if (inputs.iconState == IconState.WAITING_FOR_APPROVAL ||
            inputs.approvalQueueCount > 0
        ) {
            return base(
                iconState = if (inputs.iconState == IconState.WAITING_FOR_APPROVAL) {
                    inputs.iconState
                } else {
                    IconState.WAITING_FOR_APPROVAL
                },
                activity = JarvisAvatarActivity.GoldRing,
                pill = "Approval needed",
                line = "Waiting for your approval.",
                detail = detail,
                progress = null,
                pulse = true,
                approval = true,
                emergency = false,
                reducedMotion = inputs.reducedMotion,
            )
        }

        // 6. Speaking — both iconState SPEAKING and chatStream SPEAKING
        // count.
        if (inputs.iconState == IconState.SPEAKING ||
            inputs.chatStream == JarvisChatStreamState.SPEAKING
        ) {
            return base(
                iconState = IconState.SPEAKING,
                activity = JarvisAvatarActivity.MouthPulse,
                pill = "Speaking",
                line = "Talking it through.",
                detail = detail,
                progress = progress,
                pulse = true,
                approval = false,
                emergency = false,
                reducedMotion = inputs.reducedMotion,
            )
        }

        // 7. Listening.
        if (inputs.iconState == IconState.LISTENING) {
            return base(
                iconState = inputs.iconState,
                activity = JarvisAvatarActivity.Subtle,
                pill = "Listening",
                line = "Listening.",
                detail = detail,
                progress = null,
                pulse = true,
                approval = false,
                emergency = false,
                reducedMotion = inputs.reducedMotion,
            )
        }

        // 8. Thinking — both iconState THINKING and chatStream THINKING
        // count.
        if (inputs.iconState == IconState.THINKING ||
            inputs.chatStream == JarvisChatStreamState.THINKING
        ) {
            return base(
                iconState = IconState.THINKING,
                activity = JarvisAvatarActivity.AnimatedDots,
                pill = "Thinking",
                line = "Thinking through it.",
                detail = detail,
                progress = progress,
                pulse = true,
                approval = false,
                emergency = false,
                reducedMotion = inputs.reducedMotion,
            )
        }

        // 9. Working — split by worker phase so a 90-second background
        // task never looks idle.
        if (inputs.iconState == IconState.WORKING) {
            val (activity, pill, line) = when (inputs.workerPhase) {
                JarvisWorkerPhase.PLANNING -> Triple(
                    JarvisAvatarActivity.TaskOrbit, "Planning", "Building the plan.",
                )
                JarvisWorkerPhase.CODING -> Triple(
                    JarvisAvatarActivity.TaskOrbit, "Coding", "Editing the files.",
                )
                JarvisWorkerPhase.TESTING -> Triple(
                    JarvisAvatarActivity.CheckPulse, "Testing", "Running checks.",
                )
                JarvisWorkerPhase.REVIEWING -> Triple(
                    JarvisAvatarActivity.ScanRing, "Reviewing", "Reviewing the result.",
                )
                JarvisWorkerPhase.NONE -> Triple(
                    JarvisAvatarActivity.TaskOrbit, "Working", "Working on the task.",
                )
            }
            return base(
                iconState = inputs.iconState,
                activity = activity,
                pill = pill,
                line = line,
                detail = detail,
                progress = progress,
                pulse = true,
                approval = false,
                emergency = false,
                reducedMotion = inputs.reducedMotion,
            )
        }

        // 10. Complete — transient flash; remains "Done" until the
        // upstream window clears.
        if (inputs.iconState == IconState.COMPLETE) {
            return base(
                iconState = inputs.iconState,
                activity = JarvisAvatarActivity.CheckPulse,
                pill = "Done",
                line = "Done. Ready when you are.",
                detail = detail,
                progress = null,
                pulse = true,
                approval = false,
                emergency = false,
                reducedMotion = inputs.reducedMotion,
            )
        }

        // 11. Warning.
        if (inputs.iconState == IconState.WARNING) {
            return base(
                iconState = inputs.iconState,
                activity = JarvisAvatarActivity.Subtle,
                pill = "Heads up",
                line = "Heads up — non-fatal issue.",
                detail = detail,
                progress = null,
                pulse = true,
                approval = false,
                emergency = false,
                reducedMotion = inputs.reducedMotion,
            )
        }

        // 12. Idle floor.
        return base(
            iconState = IconState.IDLE,
            activity = JarvisAvatarActivity.Subtle,
            pill = "Idle",
            line = "Ready when you are.",
            detail = detail,
            progress = null,
            pulse = true,
            approval = false,
            emergency = false,
            reducedMotion = inputs.reducedMotion,
        )
    }

    private fun buildProgressLabel(inputs: JarvisLiveInputs): String? {
        val hasPhase = inputs.workerPhase != JarvisWorkerPhase.NONE ||
            inputs.iconState == IconState.WORKING
        if (!hasPhase) return null
        val step = inputs.activeTaskStepLabel?.takeIf { it.isNotBlank() }
        val index = inputs.activeTaskStepIndex
        val total = inputs.activeTaskStepTotal
        return when {
            step != null && index != null && total != null && total > 0 ->
                "Step $index of $total · $step"
            index != null && total != null && total > 0 ->
                "Step $index of $total"
            step != null -> step
            else -> null
        }
    }

    private fun base(
        iconState: IconState,
        activity: JarvisAvatarActivity,
        pill: String,
        line: String,
        detail: String?,
        progress: String?,
        pulse: Boolean,
        approval: Boolean,
        emergency: Boolean,
        reducedMotion: Boolean,
    ): JarvisLiveStatus {
        val safePill = pill.ifBlank { "Idle" }
        val safeLine = line.ifBlank { "Ready when you are." }
        // Reduced motion: keep the attention rings (gold / crimson)
        // because they are the legibility signal; collapse the rest to
        // Static.
        val resolvedActivity = if (!reducedMotion) {
            activity
        } else when (activity) {
            JarvisAvatarActivity.GoldRing,
            JarvisAvatarActivity.CrimsonLockedRing -> activity
            else -> JarvisAvatarActivity.Static
        }
        return JarvisLiveStatus(
            iconState = iconState,
            avatarActivity = resolvedActivity,
            statusPillText = safePill,
            statusLine = safeLine,
            detailLine = detail,
            progressLabel = progress,
            shouldPulse = pulse && !reducedMotion,
            shouldShowApprovalButton = approval,
            shouldShowEmergencyButton = emergency,
        )
    }
}
