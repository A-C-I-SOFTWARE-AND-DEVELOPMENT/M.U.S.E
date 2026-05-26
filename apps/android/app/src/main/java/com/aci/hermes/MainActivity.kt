package com.aci.hermes

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.core.content.ContextCompat
import com.aci.hermes.data.preferences.ThemeMode
import com.aci.hermes.service.HermesService
import com.aci.hermes.ui.navigation.HermesNavHost
import com.aci.hermes.ui.theme.HermesTheme

/**
 * Jarvis Prime entry activity. Permission rules:
 *  - Notifications are ONLY requested when the user taps "Enable" on
 *    the home banner or the settings row. There is no automatic
 *    permission prompt on launch.
 *  - No SMS, call log, background microphone, or overlay permissions
 *    are declared.
 */
class MainActivity : ComponentActivity() {

    private val requestNotificationPermission =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { /* handled by VM */ }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        startJarvisOrchestrator()

        val container = (application as HermesApplication).container

        setContent {
            val themePref by container.settingsRepository.themeMode.collectAsState(
                initial = ThemeMode.SYSTEM
            )
            HermesTheme(themeMode = themePref) {
                HermesNavHost(
                    container = container,
                    onRequestNotificationPermission = { requestNotificationPermissionIfNeeded() },
                )
            }
        }
    }

    private fun startJarvisOrchestrator() {
        val intent = Intent(this, HermesService::class.java).apply {
            putExtra(HermesService.EXTRA_LAUNCH_SOURCE, HermesService.DEFAULT_LAUNCH_SOURCE)
            putExtra(HermesService.EXTRA_MODE, HermesService.DEFAULT_MODE)
        }
        ContextCompat.startForegroundService(this, intent)
    }

    private fun requestNotificationPermissionIfNeeded() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) return
        val granted = ContextCompat.checkSelfPermission(
            this,
            Manifest.permission.POST_NOTIFICATIONS,
        ) == PackageManager.PERMISSION_GRANTED
        if (granted) return
        requestNotificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
    }
}
