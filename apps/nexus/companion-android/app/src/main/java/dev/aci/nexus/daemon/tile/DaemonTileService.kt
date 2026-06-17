package dev.aci.nexus.daemon.tile

import android.service.quicksettings.Tile
import android.service.quicksettings.TileService
import dev.aci.nexus.daemon.service.Credentials
import dev.aci.nexus.daemon.service.DaemonService

/** Quick Settings tile: toggle the daemon connection on/off. */
class DaemonTileService : TileService() {

    override fun onStartListening() {
        super.onStartListening()
        refresh()
    }

    override fun onClick() {
        super.onClick()
        val running = DaemonState.isRunning(this)
        if (running) {
            DaemonService.stop(this)
            DaemonState.setRunning(this, false)
        } else if (Credentials.load(this) != null) {
            DaemonService.start(this)
            DaemonState.setRunning(this, true)
        }
        refresh()
    }

    private fun refresh() {
        val tile = qsTile ?: return
        val paired = Credentials.load(this) != null
        val running = DaemonState.isRunning(this)
        tile.state = when {
            !paired -> Tile.STATE_UNAVAILABLE
            running -> Tile.STATE_ACTIVE
            else -> Tile.STATE_INACTIVE
        }
        tile.subtitle = if (running) "Connected" else "Off"
        tile.updateTile()
    }
}
