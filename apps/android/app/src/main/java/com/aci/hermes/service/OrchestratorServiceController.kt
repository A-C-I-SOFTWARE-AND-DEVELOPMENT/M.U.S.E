package com.aci.hermes.service

import android.app.ActivityManager
import android.content.Context
import android.content.Intent
import androidx.core.content.ContextCompat
import com.aci.hermes.util.LogBuffer

/**
 * Thin wrapper around the Hermes foreground service so every MUSE
 * surface (Home dashboard, Control screen, global emergency stop) starts and
 * stops the orchestrator through the same code path.
 *
 * The underlying class is still [HermesService] for technical compatibility
 * with the ADB / Termux launch contract.
 */
class OrchestratorServiceController(
    private val context: Context,
    private val logBuffer: LogBuffer,
) {

    fun isRunning(): Boolean = isServiceRunning(context, HermesService::class.java)

    fun start(launchSource: String = "ui_start") {
        val intent = Intent(context, HermesService::class.java).apply {
            putExtra(HermesService.EXTRA_LAUNCH_SOURCE, launchSource)
            putExtra(HermesService.EXTRA_MODE, HermesService.DEFAULT_MODE)
        }
        ContextCompat.startForegroundService(context, intent)
        logBuffer.info(HermesService.TAG, "Service start requested ($launchSource)")
    }

    fun stop(launchSource: String = "ui_stop") {
        context.stopService(Intent(context, HermesService::class.java))
        logBuffer.warn(HermesService.TAG, "Service stop requested ($launchSource)")
    }

    fun emergencyStop() {
        stop(launchSource = "emergency_stop")
    }

    @Suppress("DEPRECATION")
    private fun isServiceRunning(context: Context, cls: Class<*>): Boolean {
        // getRunningServices is deprecated for cross-app queries but still
        // works for the caller's own services, which is all we need.
        val am = context.getSystemService(Context.ACTIVITY_SERVICE) as? ActivityManager
            ?: return false
        return am.getRunningServices(Integer.MAX_VALUE)
            .any { it.service.className == cls.name }
    }
}
