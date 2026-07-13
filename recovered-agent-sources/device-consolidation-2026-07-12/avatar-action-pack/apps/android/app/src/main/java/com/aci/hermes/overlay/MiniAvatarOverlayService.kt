package com.aci.hermes.overlay

import android.app.Service
import android.content.Intent
import android.graphics.PixelFormat
import android.os.IBinder
import android.provider.Settings
import android.view.Gravity
import android.view.View
import android.view.WindowManager

/**
 * Minimal always-on-top mini companion service for local testing.
 *
 * The visual implementation is intentionally a placeholder View in this lane;
 * later lanes should replace it with the Compose/animated avatar surface.
 */
class MiniAvatarOverlayService : Service() {
    private var windowManager: WindowManager? = null
    private var avatarView: View? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        if (!Settings.canDrawOverlays(this)) return
        windowManager = getSystemService(WindowManager::class.java)
        avatarView = View(this).apply { alpha = 0.01f }
        val params = WindowManager.LayoutParams(
            72,
            72,
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
            PixelFormat.TRANSLUCENT,
        ).apply {
            gravity = Gravity.TOP or Gravity.START
            x = 24
            y = 240
        }
        windowManager?.addView(avatarView, params)
    }

    override fun onDestroy() {
        avatarView?.let { view -> runCatching { windowManager?.removeView(view) } }
        avatarView = null
        super.onDestroy()
    }
}
