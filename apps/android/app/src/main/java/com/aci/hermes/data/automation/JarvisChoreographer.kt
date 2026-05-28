package com.aci.hermes.data.automation

import kotlin.math.abs

/**
 * Turns a high-level [AutomationIntent] plus the current screen
 * geometry into a [MotionPlan] — the run/push/page-turn performance the
 * avatar plays while the accessibility service fires the matching real
 * gesture.
 *
 * This is the heart of the "Jarvis runs to the app and pushes it"
 * behavior, and it is deliberately **pure**: every input is a value, so
 * the coordinate math and step ordering are unit-tested without an
 * Android device.
 *
 * The visual story the steps encode:
 *  - OpenApp / PushTarget → RUN to the target, then PUSH (the press
 *    that makes the app "click"), then SETTLE. The real gesture (tap or
 *    package launch) fires on the PUSH step.
 *  - TurnPage → RUN to the screen edge, then PAGE_TURN with a wide
 *    horizontal swipe, then SETTLE.
 *  - Scroll → RUN to the content center, then SCROLL drag.
 *  - Navigate → POINT, then a global action (home/back/recents).
 */
class JarvisChoreographer(
    private val metrics: ScreenMetrics,
    private val tuning: Tuning = Tuning(),
) {

    /** Physical screen size + the avatar's current resting position. */
    data class ScreenMetrics(
        val width: Float,
        val height: Float,
        val avatarPosition: ScreenPoint,
    )

    /** All the tunable knobs in one place so tests pin exact behavior. */
    data class Tuning(
        val runSpeedPxPerMs: Float = 2.2f,
        val minRunMs: Long = 240,
        val maxRunMs: Long = 1100,
        val pushMs: Long = 360,
        val pageTurnMs: Long = 520,
        val scrollMs: Long = 600,
        val settleMs: Long = 220,
        /** How far in from the edge the page-turn swipe starts/ends. */
        val edgeInsetFraction: Float = 0.06f,
        /** Vertical band (fraction of height) the scroll drag spans. */
        val scrollSpanFraction: Float = 0.55f,
    )

    /**
     * Build the plan. [resolved] supplies on-screen bounds for the
     * target when the intent needs one (OpenApp resolves to a launchable
     * package; PushTarget resolves to a node rect). When a target can't
     * be located on screen, OpenApp still works via package launch and
     * PushTarget degrades to a center tap.
     */
    fun choreograph(intent: AutomationIntent, resolved: ResolvedTarget? = null): MotionPlan = when (intent) {
        is AutomationIntent.OpenApp -> openApp(intent, resolved)
        is AutomationIntent.PushTarget -> pushTarget(intent, resolved)
        is AutomationIntent.TurnPage -> turnPage(intent)
        is AutomationIntent.Scroll -> scroll(intent)
        is AutomationIntent.Navigate -> navigate(intent)
    }

    private fun openApp(intent: AutomationIntent.OpenApp, resolved: ResolvedTarget?): MotionPlan {
        val targetPoint = resolved?.bounds?.center ?: screenCenter()
        val gesture: DeviceGesture = resolved?.packageName
            ?.let { DeviceGesture.LaunchPackage(it) }
            ?: DeviceGesture.Tap(targetPoint)
        return plan(
            label = "Open ${intent.query}",
            steps = listOf(
                runStep(targetPoint),
                MotionStep(AvatarClip.PUSH, targetPoint, gesture, tuning.pushMs),
                settleStep(),
            ),
        )
    }

    private fun pushTarget(intent: AutomationIntent.PushTarget, resolved: ResolvedTarget?): MotionPlan {
        val targetPoint = resolved?.bounds?.center ?: screenCenter()
        return plan(
            label = "Push ${intent.query}",
            steps = listOf(
                runStep(targetPoint),
                MotionStep(AvatarClip.PUSH, targetPoint, DeviceGesture.Tap(targetPoint), tuning.pushMs),
                settleStep(),
            ),
        )
    }

    private fun turnPage(intent: AutomationIntent.TurnPage): MotionPlan {
        val inset = metrics.width * tuning.edgeInsetFraction
        val midY = metrics.height / 2f
        // To reveal the *next* (left) screen the finger swipes right→left.
        val (from, to) = when (intent.direction) {
            PageDirection.LEFT -> ScreenPoint(metrics.width - inset, midY) to ScreenPoint(inset, midY)
            PageDirection.RIGHT -> ScreenPoint(inset, midY) to ScreenPoint(metrics.width - inset, midY)
        }
        // The avatar runs to the edge it's about to "grab" (the swipe start).
        return plan(
            label = "Turn page ${intent.direction.name.lowercase()}",
            steps = listOf(
                runStep(from),
                MotionStep(
                    clip = AvatarClip.PAGE_TURN,
                    moveTo = to,
                    gesture = DeviceGesture.Swipe(from, to, tuning.pageTurnMs),
                    approxDurationMs = tuning.pageTurnMs,
                ),
                settleStep(),
            ),
        )
    }

    private fun scroll(intent: AutomationIntent.Scroll): MotionPlan {
        val centerX = metrics.width / 2f
        val span = metrics.height * tuning.scrollSpanFraction
        val midY = metrics.height / 2f
        // Scroll DOWN = content moves up = finger drags from low to high.
        val (from, to) = when (intent.direction) {
            ScrollDirection.DOWN -> ScreenPoint(centerX, midY + span / 2f) to ScreenPoint(centerX, midY - span / 2f)
            ScrollDirection.UP -> ScreenPoint(centerX, midY - span / 2f) to ScreenPoint(centerX, midY + span / 2f)
        }
        return plan(
            label = "Scroll ${intent.direction.name.lowercase()}",
            steps = listOf(
                runStep(from),
                MotionStep(
                    clip = AvatarClip.SCROLL,
                    moveTo = to,
                    gesture = DeviceGesture.Swipe(from, to, tuning.scrollMs),
                    approxDurationMs = tuning.scrollMs,
                ),
                settleStep(),
            ),
        )
    }

    private fun navigate(intent: AutomationIntent.Navigate): MotionPlan = plan(
        label = "Navigate ${intent.action.name.lowercase()}",
        steps = listOf(
            MotionStep(AvatarClip.POINT, null, DeviceGesture.Global(intent.action), tuning.pushMs),
            settleStep(),
        ),
    )

    // --- helpers -----------------------------------------------------------

    private fun runStep(to: ScreenPoint): MotionStep =
        MotionStep(AvatarClip.RUN, to, gesture = null, approxDurationMs = runDuration(to))

    private fun settleStep(): MotionStep =
        MotionStep(AvatarClip.SETTLE, moveTo = null, gesture = null, approxDurationMs = tuning.settleMs)

    private fun runDuration(to: ScreenPoint): Long {
        val dist = metrics.avatarPosition.distanceTo(to)
        val raw = (dist / tuning.runSpeedPxPerMs).toLong()
        return raw.coerceIn(tuning.minRunMs, tuning.maxRunMs)
    }

    private fun screenCenter(): ScreenPoint = ScreenPoint(metrics.width / 2f, metrics.height / 2f)

    private fun plan(label: String, steps: List<MotionStep>): MotionPlan =
        MotionPlan(intentLabel = label, origin = metrics.avatarPosition, steps = steps)

    /**
     * True when [a] and [b] are effectively the same screen position
     * (within one density-independent step). Exposed for the
     * choreographer's own short-circuits and reused by tests.
     */
    fun samePoint(a: ScreenPoint, b: ScreenPoint, epsilon: Float = 1.5f): Boolean =
        abs(a.x - b.x) <= epsilon && abs(a.y - b.y) <= epsilon
}

/**
 * What [AppTargetResolver] / the accessibility node walk hands back: an
 * on-screen rectangle and, for app launches, the resolved package.
 */
data class ResolvedTarget(
    val label: String,
    val bounds: ScreenRect?,
    val packageName: String?,
)
