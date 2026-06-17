package dev.aci.nexus.daemon.service

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import dev.aci.nexus.daemon.tile.DaemonState

/** Restart the daemon after reboot if the user had it enabled. */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Intent.ACTION_BOOT_COMPLETED) return
        if (DaemonState.isRunning(context) && Credentials.load(context) != null) {
            DaemonService.start(context)
        }
    }
}
