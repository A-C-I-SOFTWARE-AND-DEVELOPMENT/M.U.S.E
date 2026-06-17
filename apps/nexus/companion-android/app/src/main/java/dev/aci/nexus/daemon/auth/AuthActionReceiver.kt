package dev.aci.nexus.daemon.auth

import android.app.NotificationManager
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import dev.aci.nexus.daemon.net.MuseClient
import dev.aci.nexus.daemon.service.Credentials
import kotlin.concurrent.thread

/** Handles the Approve/Deny taps from the authorization notification. */
class AuthActionReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val id = intent.getStringExtra(EXTRA_ID) ?: return
        val approve = intent.getBooleanExtra(EXTRA_APPROVE, false)
        val creds = Credentials.load(context) ?: return

        thread {
            runCatching { MuseClient(creds.baseUrl, creds.token).resolveAuth(id, approve) }
        }
        (context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager)
            .cancel(id.hashCode())
    }

    companion object {
        const val EXTRA_ID = "id"
        const val EXTRA_APPROVE = "approve"
    }
}
