package dev.aci.nexus.daemon.tile

import android.content.Context

/** Tiny shared flag for whether the daemon should be running (tile + boot). */
object DaemonState {
    private const val FILE = "nexus_daemon_state"

    fun isRunning(ctx: Context): Boolean =
        ctx.getSharedPreferences(FILE, Context.MODE_PRIVATE).getBoolean("running", false)

    fun setRunning(ctx: Context, value: Boolean) {
        ctx.getSharedPreferences(FILE, Context.MODE_PRIVATE).edit()
            .putBoolean("running", value).apply()
    }
}
