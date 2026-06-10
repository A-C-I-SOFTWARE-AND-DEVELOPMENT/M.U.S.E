package com.aci.hermes.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.graphics.PixelFormat
import android.os.Build
import android.os.IBinder
import android.provider.Settings
import android.view.Gravity
import android.view.WindowManager
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.platform.ComposeView
import androidx.lifecycle.LifecycleService
import androidx.lifecycle.lifecycleScope
import com.aci.hermes.data.automation.AvatarClip
import com.aci.hermes.data.automation.MotionPlan
import com.aci.hermes.data.automation.ScreenPoint
import com.aci.hermes.data.life.AvatarBehavior
import com.aci.hermes.data.life.BehaviorScheduler
import com.aci.hermes.ui.screens.live.AvatarAnimation
import com.aci.hermes.ui.screens.live.AvatarInputs
import com.aci.hermes.ui.screens.live.JarvisLiveState
import com.aci.hermes.ui.screens.live.JarvisOverlayContent
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.launch
import kotlin.time.Duration.Companion.milliseconds

/**
 * Jarvis' body on screen. A foreground service that draws the living
 * avatar in a [WindowManager] overlay window (`TYPE_APPLICATION_OVERLAY`)
 * so it floats over every app — the literal "lives on your screen"
 * surface. It owns:
 *
 *  - the avatar's on-screen position (animated as it "runs"),
 *  - the [BehaviorScheduler] life loop (idle/wander/sleep/recommend),
 *  - execution of a [MotionPlan]: animate the run, then ask
 *    [JarvisAccessibilityService] to fire the real gesture on the PUSH
 *    / PAGE_TURN step so the app visibly clicks / the page flips.
 *
 * Start it from Jarvis Live once `Settings.canDrawOverlays` is granted.
 */
class JarvisOverlayService : LifecycleService() {

    private lateinit var windowManager: WindowManager
    private var overlayView: ComposeView? = null
    private lateinit var layoutParams: WindowManager.LayoutParams

    private val scheduler = BehaviorScheduler()

    private val position = MutableStateFlow(ScreenPoint(120f, 400f))
    private val behavior = MutableStateFlow(AvatarBehavior.IDLE)
    private val activeClip = MutableStateFlow<AvatarClip?>(null)
    private val liveState = MutableStateFlow(JarvisLiveState.Idle)

    private var lastInteractionMs: Long = now()

    override fun onCreate() {
        super.onCreate()
        windowManager = getSystemService(Context.WINDOW_SERVICE) as WindowManager
        startInForeground()
        addOverlay()
        startLifeLoop()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        super.onStartCommand(intent, flags, startId)
        return START_STICKY
    }

    override fun onBind(intent: Intent): IBinder? {
        super.onBind(intent)
        return null
    }

    override fun onDestroy() {
        overlayView?.let { runCatching { windowManager.removeView(it) } }
        overlayView = null
        if (active === this) active = null
        super.onDestroy()
    }

    // --- public control surface -------------------------------------------

    /** Drive the avatar's work state from the agent state feed. */
    fun setLiveState(state: JarvisLiveState) {
        liveState.value = state
        lastInteractionMs = now()
    }

    /**
     * Play a full motion plan: ease the avatar to each step's target,
     * then dispatch the real gesture (if any) once the "push" lands.
     */
    fun execute(plan: MotionPlan) {
        lifecycleScope.launch {
            lastInteractionMs = now()
            for (step in plan.steps) {
                activeClip.value = step.clip
                step.moveTo?.let { animateTo(it, step.approxDurationMs) }
                step.gesture?.let { gesture ->
                    JarvisAccessibilityService.instance?.perform(gesture)
                }
                if (step.moveTo == null) delay(step.approxDurationMs.milliseconds)
            }
            activeClip.value = null
        }
    }

    // --- internals ---------------------------------------------------------

    private suspend fun animateTo(target: ScreenPoint, durationMs: Long) {
        val start = position.value
        val frames = (durationMs / FRAME_MS).toInt().coerceAtLeast(1)
        for (i in 1..frames) {
            val t = i.toFloat() / frames
            // ease-in-out for a less robotic run
            val e = t * t * (3 - 2 * t)
            position.value = ScreenPoint(
                start.x + (target.x - start.x) * e,
                start.y + (target.y - start.y) * e,
            )
            layoutParams.x = position.value.x.toInt()
            layoutParams.y = position.value.y.toInt()
            overlayView?.let { runCatching { windowManager.updateViewLayout(it, layoutParams) } }
            delay(FRAME_MS.milliseconds)
        }
    }

    private fun startLifeLoop() {
        lifecycleScope.launch {
            while (true) {
                val idleFor = (now() - lastInteractionMs).milliseconds
                val tick = BehaviorScheduler.Tick(
                    idleFor = idleFor,
                    localHour = java.time.LocalTime.now().hour,
                    hasPendingRecommendation = false,
                    sinceLastRecommendation = kotlin.time.Duration.INFINITE,
                    agentBusy = liveState.value != JarvisLiveState.Idle,
                )
                behavior.value = scheduler.decide(tick)
                delay(LIFE_TICK_MS.milliseconds)
            }
        }
    }

    private fun addOverlay() {
        if (!Settings.canDrawOverlays(this)) {
            stopSelf()
            return
        }
        val type = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
        } else {
            @Suppress("DEPRECATION")
            WindowManager.LayoutParams.TYPE_PHONE
        }
        layoutParams = WindowManager.LayoutParams(
            OVERLAY_SIZE_PX,
            OVERLAY_SIZE_PX,
            type,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL or
                WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
            PixelFormat.TRANSLUCENT,
        ).apply {
            gravity = Gravity.TOP or Gravity.START
            x = position.value.x.toInt()
            y = position.value.y.toInt()
        }

        val view = ComposeView(this).apply {
            setContent {
                val inputs = currentInputs()
                JarvisOverlayContent(inputs)
            }
        }
        overlayView = view
        runCatching { windowManager.addView(view, layoutParams) }
        active = this
    }

    @androidx.compose.runtime.Composable
    private fun currentInputs(): AvatarInputs {
        val state by liveState.collectAsState()
        val beh by behavior.collectAsState()
        val clip by activeClip.collectAsState()
        return AvatarAnimation.inputsFor(
            state = state,
            behavior = beh,
            activeClip = clip,
            motionEnabled = true,
        )
    }

    private fun startInForeground() {
        val channelId = "jarvis_overlay"
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val nm = getSystemService(NotificationManager::class.java)
            nm.createNotificationChannel(
                NotificationChannel(channelId, "Muse presence", NotificationManager.IMPORTANCE_LOW),
            )
        }
        val notification: Notification = Notification.Builder(this, channelId)
            .setContentTitle("Muse is on screen")
            .setContentText("Tap the avatar to talk · long-press to dismiss")
            .setSmallIcon(com.aci.hermes.R.mipmap.ic_launcher)
            .build()
        // The typed 3-arg startForeground is API 29+, and the SPECIAL_USE
        // type is API 34+. Guard directly on SDK_INT so lint's flow
        // analysis is satisfied; below 34 fall back to the 2-arg form
        // (the manifest's specialUse type is simply ignored there).
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            startForeground(
                OVERLAY_NOTIFICATION_ID,
                notification,
                android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE,
            )
        } else {
            @Suppress("DEPRECATION")
            startForeground(OVERLAY_NOTIFICATION_ID, notification)
        }
    }

    private fun now(): Long = System.currentTimeMillis()

    companion object {
        @Volatile
        var active: JarvisOverlayService? = null
            private set

        const val OVERLAY_NOTIFICATION_ID = 4242
        const val OVERLAY_SIZE_PX = 320
        private const val FRAME_MS = 16L
        private const val LIFE_TICK_MS = 1500L

        fun start(context: Context) {
            val intent = Intent(context, JarvisOverlayService::class.java)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(intent)
            } else {
                context.startService(intent)
            }
        }

        fun stop(context: Context) {
            context.stopService(Intent(context, JarvisOverlayService::class.java))
        }

        /** True once the overlay permission has been granted. */
        fun canDraw(context: Context): Boolean = Settings.canDrawOverlays(context)
    }
}
