package com.aci.hermes.service

import android.app.Notification
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.lifecycle.LifecycleService
import androidx.lifecycle.lifecycleScope
import com.aci.hermes.HermesApplication
import com.aci.hermes.MainActivity
import com.aci.hermes.R
import com.aci.hermes.notify.WorkWatcher
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

/**
 * Foreground (`dataSync`) service that keeps the [WorkWatcher] polling while
 * the app is backgrounded, so a notification can pull the owner back to a job
 * that finished or blocked after they left.
 *
 * Lifecycle, by design (no permanent always-on poller):
 *  - **Started only when active work exists** — the in-app foreground poller
 *    (see [com.aci.hermes.di.AppContainer.onAppForeground]) starts it the
 *    moment it sees a non-terminal job or a pending approval.
 *  - **Self-stops** after [IDLE_TICKS_BEFORE_STOP] consecutive idle ticks once
 *    no active work remains.
 *  - **Backs off** exponentially on consecutive poll errors.
 *
 * It reuses the existing `hermes_orchestrator` channel for its ongoing notice
 * so it does not add a second persistent channel to the user's settings.
 */
class WorkWatchService : LifecycleService() {

    /** Whether this instance's poll loop is already running (guards repeat starts). */
    @Volatile
    private var running = false

    override fun onCreate() {
        super.onCreate()
        HermesService.ensureNotificationChannel(this)
        startInForeground()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        super.onStartCommand(intent, flags, startId)
        if (!running) {
            running = true
            lifecycleScope.launch { pollLoop() }
        }
        return START_STICKY
    }

    override fun onDestroy() {
        running = false
        super.onDestroy()
    }

    private suspend fun pollLoop() {
        val container = (application as HermesApplication).container
        val watcher = container.workWatcher
        var backoffMs = MIN_BACKOFF_MS
        var idleTicks = 0
        var errorTicks = 0

        while (lifecycleScope.coroutineContext.isActive && running) {
            val result = watcher.tick()

            if (result.error) {
                // Don't pin a foreground service to a dead gateway forever:
                // back off, but give up after enough consecutive failures.
                // The in-app foreground poller restarts us when the app is
                // reopened (and the gateway is hopefully reachable again).
                if (++errorTicks >= MAX_ERROR_TICKS_BEFORE_STOP) {
                    Log.w(TAG, "gateway unreachable for $errorTicks polls — standing down")
                    stopSelf()
                    break
                }
                Log.w(TAG, "poll error ($errorTicks) — backing off ${backoffMs}ms")
                delay(backoffMs)
                backoffMs = (backoffMs * 2).coerceAtMost(MAX_BACKOFF_MS)
                continue
            }
            errorTicks = 0
            backoffMs = MIN_BACKOFF_MS

            if (result.hasActiveWork) {
                idleTicks = 0
            } else if (++idleTicks >= IDLE_TICKS_BEFORE_STOP) {
                Log.i(TAG, "no active work — standing down")
                stopSelf()
                break
            }

            val intervalSec = container.settingsRepository.notificationPollIntervalSeconds.first()
            delay(intervalSec.coerceIn(MIN_INTERVAL_SEC, MAX_INTERVAL_SEC) * 1000L)
        }
    }

    private fun startInForeground() {
        val openApp = android.app.PendingIntent.getActivity(
            this,
            0,
            Intent(this, MainActivity::class.java).apply { flags = Intent.FLAG_ACTIVITY_SINGLE_TOP },
            android.app.PendingIntent.FLAG_UPDATE_CURRENT or android.app.PendingIntent.FLAG_IMMUTABLE,
        )
        val notification: Notification = NotificationCompat.Builder(this, HermesService.CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_launcher_foreground)
            .setContentTitle(getString(R.string.workwatch_notification_title))
            .setContentText(getString(R.string.workwatch_notification_text))
            .setContentIntent(openApp)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            startForeground(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)
        } else {
            startForeground(NOTIFICATION_ID, notification)
        }
    }

    companion object {
        const val TAG = "WorkWatchService"
        private const val NOTIFICATION_ID = 1002

        private const val MIN_BACKOFF_MS = 5_000L
        private const val MAX_BACKOFF_MS = 120_000L
        private const val IDLE_TICKS_BEFORE_STOP = 2
        private const val MAX_ERROR_TICKS_BEFORE_STOP = 5
        private const val MIN_INTERVAL_SEC = 10L
        private const val MAX_INTERVAL_SEC = 600L

        fun start(context: Context) {
            val intent = Intent(context, WorkWatchService::class.java)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(intent)
            } else {
                context.startService(intent)
            }
        }

        fun stop(context: Context) {
            context.stopService(Intent(context, WorkWatchService::class.java))
        }
    }
}
