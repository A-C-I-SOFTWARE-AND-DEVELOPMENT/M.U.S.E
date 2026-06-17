package dev.aci.nexus.daemon.widget

import android.content.Context
import dev.aci.nexus.daemon.net.StatusSnapshot

/** Last cached status snapshot, read by the widget and the QS tile. */
object StatusStore {
    private const val FILE = "nexus_status"

    fun save(ctx: Context, s: StatusSnapshot) {
        ctx.getSharedPreferences(FILE, Context.MODE_PRIVATE).edit()
            .putInt("idle", s.idle)
            .putInt("running", s.running)
            .putInt("error", s.error)
            .putInt("needsAuth", s.needsAuth)
            .apply()
        StatusWidgetReceiver.requestUpdate(ctx)
    }

    fun load(ctx: Context): StatusSnapshot {
        val p = ctx.getSharedPreferences(FILE, Context.MODE_PRIVATE)
        return StatusSnapshot(
            idle = p.getInt("idle", 0),
            running = p.getInt("running", 0),
            error = p.getInt("error", 0),
            needsAuth = p.getInt("needsAuth", 0),
        )
    }
}
