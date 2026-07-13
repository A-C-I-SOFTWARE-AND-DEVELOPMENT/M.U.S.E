package com.aci.hermes.automation

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.graphics.Path
import android.graphics.PointF
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo

/**
 * Owner-authorized personal-use accessibility broker.
 *
 * This service is intentionally small: locate a visible clickable node first,
 * then fall back to a direct tap gesture only when node action is unavailable.
 * Higher-level reasoning and task selection remain in Hermes/JARVIS.
 */
class JarvisAccessibilityService : AccessibilityService() {

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        // Future lane: update screen model for the mini avatar. Keep this
        // callback side-effect-light so it does not become a hidden recorder.
    }

    override fun onInterrupt() {
        // No persistent action to clean up.
    }

    fun clickFirstNodeContaining(label: String): Boolean {
        val root = rootInActiveWindow ?: return false
        val target = findClickableNode(root, label.lowercase()) ?: return false
        return target.performAction(AccessibilityNodeInfo.ACTION_CLICK)
    }

    fun tap(point: PointF, onResult: GestureResultCallback? = null): Boolean {
        val path = Path().apply { moveTo(point.x, point.y) }
        val gesture = GestureDescription.Builder()
            .addStroke(GestureDescription.StrokeDescription(path, 0, TAP_DURATION_MS))
            .build()
        return dispatchGesture(gesture, onResult, null)
    }

    private fun findClickableNode(node: AccessibilityNodeInfo, needle: String): AccessibilityNodeInfo? {
        val text = listOfNotNull(node.text, node.contentDescription)
            .joinToString(" ")
            .lowercase()
        if (node.isClickable && needle in text) return node
        for (i in 0 until node.childCount) {
            val child = node.getChild(i) ?: continue
            val found = findClickableNode(child, needle)
            if (found != null) return found
        }
        return null
    }

    companion object {
        private const val TAP_DURATION_MS = 80L
    }
}
