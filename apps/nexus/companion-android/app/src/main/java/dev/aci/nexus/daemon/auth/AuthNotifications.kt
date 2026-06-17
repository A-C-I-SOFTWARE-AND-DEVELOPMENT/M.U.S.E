package dev.aci.nexus.daemon.auth

import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import androidx.core.app.NotificationCompat
import dev.aci.nexus.daemon.net.AuthRequest
import dev.aci.nexus.daemon.service.DaemonService

/**
 * Owner-gated authorization relay. When M.U.S.E. defers an action it sends an
 * auth-request frame; we fire a high-priority Approve/Deny notification. The
 * daemon forwards the decision; M.U.S.E. enforces policy server-side.
 */
object AuthNotifications {
    fun fire(ctx: Context, req: AuthRequest) {
        val approve = action(ctx, req.id, true, "Approve")
        val deny = action(ctx, req.id, false, "Deny")

        val n = NotificationCompat.Builder(ctx, DaemonService.CH_AUTH)
            .setContentTitle("M.U.S.E. needs authorization")
            .setContentText(req.action)
            .setStyle(NotificationCompat.BigTextStyle().bigText("${req.action}\nRisk: ${req.risk}"))
            .setSmallIcon(android.R.drawable.ic_lock_lock)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setCategory(NotificationCompat.CATEGORY_CALL)
            .setAutoCancel(true)
            .addAction(android.R.drawable.ic_menu_close_clear_cancel, "Deny", deny)
            .addAction(android.R.drawable.checkbox_on_background, "Approve", approve)
            .build()

        (ctx.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager)
            .notify(req.id.hashCode(), n)
    }

    private fun action(ctx: Context, id: String, approve: Boolean, label: String): PendingIntent {
        val intent = Intent(ctx, AuthActionReceiver::class.java).apply {
            this.action = "dev.aci.nexus.AUTH_$label"
            putExtra(AuthActionReceiver.EXTRA_ID, id)
            putExtra(AuthActionReceiver.EXTRA_APPROVE, approve)
        }
        return PendingIntent.getBroadcast(
            ctx, (id + label).hashCode(), intent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
    }
}
