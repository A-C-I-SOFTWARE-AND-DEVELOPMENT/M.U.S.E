package com.aci.hermes.data.automation

/**
 * A device coordinate in screen pixels. Kept as a plain data class with
 * no Android dependency so the choreographer and its tests share one
 * shape (mirrors the `data/jarvis` pure-logic convention).
 */
data class ScreenPoint(val x: Float, val y: Float) {
    fun distanceTo(other: ScreenPoint): Float {
        val dx = other.x - x
        val dy = other.y - y
        return kotlin.math.sqrt(dx * dx + dy * dy)
    }
}

/** Rectangular bounds of an on-screen target (an icon, a button, …). */
data class ScreenRect(val left: Float, val top: Float, val right: Float, val bottom: Float) {
    val centerX: Float get() = (left + right) / 2f
    val centerY: Float get() = (top + bottom) / 2f
    val center: ScreenPoint get() = ScreenPoint(centerX, centerY)
    val width: Float get() = right - left
    val height: Float get() = bottom - top
}

/**
 * The visible animation the avatar performs while it carries out a
 * real device action. The [JarvisAccessibilityService] plays the clip
 * named here while it dispatches the matching gesture.
 */
enum class AvatarClip {
    RUN,        // travel across the screen toward a target
    PUSH,       // press an app / button with the hand → it "clicks"
    PAGE_TURN,  // grab the screen edge and flip to the next home screen
    SCROLL,     // drag content
    POINT,      // gesture at a target without acting (e.g. a recommendation)
    SETTLE,     // ease back to idle after an action
}

/**
 * The concrete gesture the accessibility service must dispatch. The
 * choreographer only ever produces these; it never touches the
 * platform directly, so the whole plan is unit-testable.
 */
sealed interface DeviceGesture {
    /** A single tap at [point]. */
    data class Tap(val point: ScreenPoint) : DeviceGesture

    /** A swipe from [from] to [to] over [durationMs]. */
    data class Swipe(
        val from: ScreenPoint,
        val to: ScreenPoint,
        val durationMs: Long,
    ) : DeviceGesture

    /** Launch an installed app by package name (no coordinate needed). */
    data class LaunchPackage(val packageName: String) : DeviceGesture

    /** A global navigation action (home / back / recents). */
    data class Global(val action: GlobalAction) : DeviceGesture
}

enum class GlobalAction { HOME, BACK, RECENTS }

/**
 * One step of the avatar's performance: walk somewhere, play a clip,
 * then (optionally) fire a real gesture at the end of the clip.
 *
 * `gesture == null` means a purely cosmetic step (e.g. RUN to a spot
 * before the acting step). Steps are executed in order.
 */
data class MotionStep(
    val clip: AvatarClip,
    val moveTo: ScreenPoint?,
    val gesture: DeviceGesture?,
    val approxDurationMs: Long,
)

/**
 * The full performance for a single high-level intent. The avatar
 * starts at [origin], runs through [steps], and finishes back in an
 * idle posture.
 */
data class MotionPlan(
    val intentLabel: String,
    val origin: ScreenPoint,
    val steps: List<MotionStep>,
) {
    val totalDurationMs: Long get() = steps.sumOf { it.approxDurationMs }

    /** The real gestures this plan will fire, in order — handy for tests. */
    val gestures: List<DeviceGesture> get() = steps.mapNotNull { it.gesture }
}
