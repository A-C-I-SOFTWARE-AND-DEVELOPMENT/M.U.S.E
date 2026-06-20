package com.aci.hermes.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import android.util.Log
import androidx.core.app.NotificationCompat
import com.aci.hermes.MainActivity
import com.aci.hermes.R
import com.aci.hermes.notify.DeepLink
import com.aci.hermes.ui.navigation.Screen

/**
 * Local-only foreground service. Keeps a visible notification so the user
 * always knows the orchestrator is running. Holds no business logic — no
 * HTTP calls, no shell, no scraping. Local orchestration state lives in
 * the process-scoped [com.aci.hermes.data.orchestrator.HermesTaskRepository].
 */
class HermesService : Service() {

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        ensureNotificationChannel(this)
        Log.i(TAG, "HermesService created")
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val launchSource = intent?.getStringExtra(EXTRA_LAUNCH_SOURCE) ?: DEFAULT_LAUNCH_SOURCE
        // Prefer the namespaced `hermes_mode` extra used by `adb shell am
        // start-foreground-service` invocations from Termux / CI; fall back to
        // the legacy `mode` key for in-process Intents built before the
        // namespacing convention landed.
        val mode = intent?.getStringExtra(EXTRA_HERMES_MODE)
            ?: intent?.getStringExtra(EXTRA_MODE)
            ?: DEFAULT_MODE
        val workspace = intent?.getStringExtra(EXTRA_HERMES_WORKSPACE)
        val agent = intent?.getStringExtra(EXTRA_HERMES_AGENT)
        val debug = intent?.getBooleanExtra(EXTRA_HERMES_DEBUG, false) == true

        // Handle in-notification Stop action.
        if (intent?.action == ACTION_STOP) {
            Log.i(TAG, "Hermes orchestrator stop requested via notification")
            stopSelf()
            return START_NOT_STICKY
        }

        Log.i(TAG, "Hermes local orchestrator started")
        Log.i(TAG, "Launch source: $launchSource")
        Log.i(TAG, "Mode: $mode")
        // The service stays local-only — these extras are recorded for
        // observability so an ADB-triggered start surfaces what the caller
        // intended. Routing them into a real Python/CLI bridge is tracked
        // separately (see apps/android/README.md → "Service intent contract").
        if (workspace != null) Log.i(TAG, "Workspace hint: $workspace")
        if (agent != null) Log.i(TAG, "Agent hint: $agent")
        if (debug) Log.i(TAG, "Debug mode requested")

        val notification = buildNotification()
        // On API 34+ the typed overload is required when the manifest
        // declares a foregroundServiceType.
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            startForeground(
                NOTIFICATION_ID,
                notification,
                ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC
            )
        } else {
            startForeground(NOTIFICATION_ID, notification)
        }

        return START_STICKY
    }

    override fun onDestroy() {
        Log.i(TAG, "HermesService stopped")
        super.onDestroy()
    }

    private fun buildNotification(): Notification {
        val openAppIntent = PendingIntent.getActivity(
            this,
            0,
            Intent(this, MainActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_SINGLE_TOP
            },
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val stopIntent = PendingIntent.getService(
            this,
            1,
            Intent(this, HermesService::class.java).setAction(ACTION_STOP),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        // Owner-approve action deep-links into MainActivity, which routes to
        // the Approvals screen. The decision there still goes through the
        // owner gate (the exact phrase "Yes, with authorization."); this
        // action only opens the queue. (Previously this set a `jarvis_action`
        // extra that nothing consumed — a dead path now wired to the canonical
        // notification deep-link contract in [DeepLink].)
        val ownerApproveIntent = PendingIntent.getActivity(
            this,
            2,
            Intent(this, MainActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_SINGLE_TOP
                putExtra(DeepLink.EXTRA_NAV_ROUTE, Screen.Approvals.route)
            },
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_launcher_foreground)
            .setContentTitle(getString(R.string.orchestrator_notification_title))
            .setContentText(getString(R.string.orchestrator_notification_text))
            .setContentIntent(openAppIntent)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .addAction(
                NotificationCompat.Action.Builder(
                    0,
                    getString(R.string.orchestrator_notification_owner_approve),
                    ownerApproveIntent
                ).build()
            )
            .addAction(
                NotificationCompat.Action.Builder(
                    0,
                    getString(R.string.orchestrator_notification_stop),
                    stopIntent
                ).build()
            )
            .build()
    }

    companion object {
        const val TAG = "HermesService"
        // Channel ID stays `hermes_orchestrator` so a user's customized
        // importance/visibility survives the rebrand. The display NAME is
        // what shows in Android Settings → Notifications, so it carries the
        // muse identity.
        const val CHANNEL_ID = "hermes_orchestrator"
        private const val CHANNEL_NAME = "muse"
        private const val NOTIFICATION_ID = 1001
        const val ACTION_STOP = "com.aci.hermes.action.STOP_ORCHESTRATOR"

        const val EXTRA_LAUNCH_SOURCE = "launch_source"
        const val EXTRA_MODE = "mode"

        // Namespaced extras for ADB / Termux launches. Keeping the
        // `hermes_*` prefix lets a caller pass the same payload across
        // the Python CLI, the Termux bridge, and `am start-foreground-service`
        // without collisions with platform-defined extras.
        const val EXTRA_HERMES_WORKSPACE = "hermes_workspace"
        const val EXTRA_HERMES_MODE = "hermes_mode"
        const val EXTRA_HERMES_AGENT = "hermes_agent"
        const val EXTRA_HERMES_DEBUG = "hermes_debug"

        const val DEFAULT_LAUNCH_SOURCE = "app_start"
        const val DEFAULT_MODE = "local_subscription_tools"

        fun ensureNotificationChannel(context: Context) {
            if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
            val manager = context.getSystemService(NotificationManager::class.java) ?: return
            if (manager.getNotificationChannel(CHANNEL_ID) != null) return
            val channel = NotificationChannel(
                CHANNEL_ID,
                CHANNEL_NAME,
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Persistent indicator that muse is coordinating local AI workflows."
                setShowBadge(false)
            }
            manager.createNotificationChannel(channel)
        }
    }
}
