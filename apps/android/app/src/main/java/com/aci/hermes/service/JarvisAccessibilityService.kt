package com.aci.hermes.service

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.content.Intent
import android.graphics.Path
import android.graphics.Rect
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import com.aci.hermes.data.automation.AppTargetResolver
import com.aci.hermes.data.automation.DeviceGesture
import com.aci.hermes.data.automation.GlobalAction
import com.aci.hermes.data.automation.MotionPlan
import com.aci.hermes.data.automation.ScreenPoint
import com.aci.hermes.data.automation.ScreenRect
import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.CompletableDeferred

/**
 * Jarvis' "hands". Bound as an [AccessibilityService] so Jarvis can
 * physically operate the phone: dispatch the real taps/swipes a
 * [MotionPlan] calls for, launch apps, and read the on-screen node tree
 * to find where a target lives. The avatar performance (run-to-icon,
 * push, page-turn) is choreographed in [JarvisOverlayService]; this
 * service fires the matching gesture at the moment the "push" lands.
 *
 * Security note: this is a personal-tool fork, so the usual permission
 * restraint is intentionally lifted. The service still honors the
 * emergency stop — when [EmergencyStopController] is engaged, every
 * gesture is dropped.
 */
class JarvisAccessibilityService : AccessibilityService() {

    private val log = LogBuffer()

    override fun onServiceConnected() {
        super.onServiceConnected()
        instance = this
        log.info("jarvis-a11y", "JarvisAccessibilityService connected")
    }

    override fun onDestroy() {
        if (instance === this) instance = null
        super.onDestroy()
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) { /* node tree read on demand */ }

    override fun onInterrupt() { /* no long-running gesture state to clear */ }

    /** Dispatch a single gesture, suspending until the system reports done. */
    suspend fun perform(gesture: DeviceGesture): Boolean {
        if (gestureGuard?.invoke() == false) {
            log.warn("jarvis-a11y", "Gesture blocked by emergency stop: $gesture")
            return false
        }
        return when (gesture) {
            is DeviceGesture.Tap -> dispatchTap(gesture.point)
            is DeviceGesture.Swipe -> dispatchSwipe(gesture.from, gesture.to, gesture.durationMs)
            is DeviceGesture.LaunchPackage -> launchPackage(gesture.packageName)
            is DeviceGesture.Global -> performGlobal(gesture.action)
        }
    }

    /** Snapshot the currently launchable apps + visible icon bounds. */
    fun installedApps(): List<AppTargetResolver.InstalledApp> {
        val pm = packageManager
        val launcher = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
        val visibleIcons = scrapeLauncherIcons()
        return pm.queryIntentActivities(launcher, 0).mapNotNull { ri ->
            val pkg = ri.activityInfo?.packageName ?: return@mapNotNull null
            val label = ri.loadLabel(pm).toString()
            AppTargetResolver.InstalledApp(
                packageName = pkg,
                label = label,
                iconBounds = visibleIcons[label] ?: visibleIcons[pkg],
            )
        }
    }

    /** Find the on-screen rect of a node whose text/desc matches [query]. */
    fun resolveOnScreen(query: String): ScreenRect? {
        val root = rootInActiveWindow ?: return null
        val match = findNode(root) { node ->
            val text = node.text?.toString()?.lowercase().orEmpty()
            val desc = node.contentDescription?.toString()?.lowercase().orEmpty()
            val q = query.lowercase()
            node.isVisibleToUser && (q in text || q in desc)
        } ?: return null
        val r = Rect().also { match.getBoundsInScreen(it) }
        return ScreenRect(r.left.toFloat(), r.top.toFloat(), r.right.toFloat(), r.bottom.toFloat())
    }

    private fun dispatchTap(point: ScreenPoint): Boolean {
        val path = Path().apply { moveTo(point.x, point.y) }
        val stroke = GestureDescription.StrokeDescription(path, 0, 60)
        return dispatchBlocking(GestureDescription.Builder().addStroke(stroke).build())
    }

    private fun dispatchSwipe(from: ScreenPoint, to: ScreenPoint, durationMs: Long): Boolean {
        val path = Path().apply {
            moveTo(from.x, from.y)
            lineTo(to.x, to.y)
        }
        val stroke = GestureDescription.StrokeDescription(path, 0, durationMs.coerceAtLeast(1))
        return dispatchBlocking(GestureDescription.Builder().addStroke(stroke).build())
    }

    private fun launchPackage(pkg: String): Boolean {
        val intent = packageManager.getLaunchIntentForPackage(pkg)?.apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        } ?: return false
        startActivity(intent)
        return true
    }

    private fun performGlobal(action: GlobalAction): Boolean = performGlobalAction(
        when (action) {
            GlobalAction.HOME -> GLOBAL_ACTION_HOME
            GlobalAction.BACK -> GLOBAL_ACTION_BACK
            GlobalAction.RECENTS -> GLOBAL_ACTION_RECENTS
        },
    )

    private fun dispatchBlocking(gesture: GestureDescription): Boolean {
        val done = CompletableDeferred<Boolean>()
        val ok = dispatchGesture(
            gesture,
            object : GestureResultCallback() {
                override fun onCompleted(d: GestureDescription?) { done.complete(true) }
                override fun onCancelled(d: GestureDescription?) { done.complete(false) }
            },
            null,
        )
        // dispatchGesture returns false synchronously if it couldn't be queued.
        return ok
    }

    private fun scrapeLauncherIcons(): Map<String, ScreenRect> {
        val root = rootInActiveWindow ?: return emptyMap()
        val out = HashMap<String, ScreenRect>()
        walk(root) { node ->
            val label = node.contentDescription?.toString() ?: node.text?.toString()
            if (!label.isNullOrBlank() && node.isVisibleToUser) {
                val r = Rect().also { node.getBoundsInScreen(it) }
                if (r.width() in 1..400 && r.height() in 1..400) {
                    out[label] = ScreenRect(r.left.toFloat(), r.top.toFloat(), r.right.toFloat(), r.bottom.toFloat())
                }
            }
        }
        return out
    }

    private inline fun walk(node: AccessibilityNodeInfo, visit: (AccessibilityNodeInfo) -> Unit) {
        val stack = ArrayDeque<AccessibilityNodeInfo>()
        stack.addLast(node)
        while (stack.isNotEmpty()) {
            val n = stack.removeLast()
            visit(n)
            for (i in 0 until n.childCount) n.getChild(i)?.let { stack.addLast(it) }
        }
    }

    private fun findNode(
        root: AccessibilityNodeInfo,
        predicate: (AccessibilityNodeInfo) -> Boolean,
    ): AccessibilityNodeInfo? {
        val stack = ArrayDeque<AccessibilityNodeInfo>()
        stack.addLast(root)
        while (stack.isNotEmpty()) {
            val n = stack.removeLast()
            if (predicate(n)) return n
            for (i in 0 until n.childCount) n.getChild(i)?.let { stack.addLast(it) }
        }
        return null
    }

    companion object {
        /** Live handle so the overlay service can drive gestures. */
        @Volatile
        var instance: JarvisAccessibilityService? = null
            private set

        /** Returns false to drop all gestures (wired to emergency stop). */
        @Volatile
        var gestureGuard: (() -> Boolean)? = null

        val isConnected: Boolean get() = instance != null
    }
}
