package dev.aci.nexus.daemon.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.core.app.NotificationCompat
import androidx.lifecycle.LifecycleService
import androidx.lifecycle.lifecycleScope
import dev.aci.nexus.daemon.auth.AuthNotifications
import dev.aci.nexus.daemon.net.DaemonFrame
import dev.aci.nexus.daemon.net.MuseClient
import dev.aci.nexus.daemon.net.StatusSnapshot
import dev.aci.nexus.daemon.widget.StatusStore
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import okhttp3.WebSocket

/**
 * Persistent foreground service. Holds the M.U.S.E. socket open so status and
 * owner-gated authorization prompts arrive even when the PWA is closed. Thin:
 * it routes frames to notifications + the cached status snapshot. No UI.
 */
class DaemonService : LifecycleService() {

    private var socket: WebSocket? = null
    private lateinit var client: MuseClient

    override fun onCreate() {
        super.onCreate()
        createChannels()
        startForeground(ONGOING_ID, buildOngoing(StatusSnapshot()))
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        super.onStartCommand(intent, flags, startId)
        val creds = Credentials.load(this) ?: return START_NOT_STICKY
        client = MuseClient(creds.baseUrl, creds.token)
        connectWithRetry()
        return START_STICKY
    }

    private fun connectWithRetry() {
        lifecycleScope.launch {
            var backoff = 2000L
            while (true) {
                val connected = openSocket()
                if (connected) backoff = 2000L
                delay(backoff)
                backoff = (backoff * 2).coerceAtMost(60_000L)
            }
        }
    }

    private fun openSocket(): Boolean = try {
        socket = client.connect(
            onFrame = ::handleFrame,
            onClosed = { socket = null },
        )
        true
    } catch (_: Exception) {
        false
    }

    private fun handleFrame(frame: DaemonFrame) {
        when (frame) {
            is DaemonFrame.Status -> {
                StatusStore.save(this, frame.snapshot)
                notify(ONGOING_ID, buildOngoing(frame.snapshot))
            }
            is DaemonFrame.Event -> { /* surfaced in PWA activity feed; widget shows counts */ }
            is DaemonFrame.Auth -> AuthNotifications.fire(this, frame.request)
        }
    }

    private fun buildOngoing(s: StatusSnapshot): Notification {
        val total = s.idle + s.running + s.error + s.needsAuth
        return NotificationCompat.Builder(this, CH_ONGOING)
            .setContentTitle("NEXUS daemon active")
            .setContentText("$total agents · ${s.running} running · ${s.error} error")
            .setSmallIcon(android.R.drawable.stat_sys_data_bluetooth) // placeholder glyph
            .setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_MIN)
            .setContentIntent(openPwa("/agents"))
            .build()
    }

    private fun openPwa(path: String): PendingIntent {
        val host = Credentials.load(this)?.pwaHost ?: "https://nexus.local"
        val intent = Intent(Intent.ACTION_VIEW, Uri.parse("$host$path"))
        return PendingIntent.getActivity(
            this, path.hashCode(), intent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
    }

    private fun notify(id: Int, n: Notification) =
        (getSystemService(NOTIFICATION_SERVICE) as NotificationManager).notify(id, n)

    private fun createChannels() {
        val mgr = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        mgr.createNotificationChannel(
            NotificationChannel(CH_ONGOING, "Daemon status", NotificationManager.IMPORTANCE_MIN)
        )
        mgr.createNotificationChannel(
            NotificationChannel(CH_AUTH, "Authorization", NotificationManager.IMPORTANCE_HIGH)
        )
    }

    override fun onDestroy() {
        socket?.cancel()
        super.onDestroy()
    }

    companion object {
        const val CH_ONGOING = "nexus_ongoing"
        const val CH_AUTH = "nexus_auth"
        const val ONGOING_ID = 1001

        fun start(ctx: Context) =
            ctx.startForegroundService(Intent(ctx, DaemonService::class.java))

        fun stop(ctx: Context) = ctx.stopService(Intent(ctx, DaemonService::class.java))
    }
}
