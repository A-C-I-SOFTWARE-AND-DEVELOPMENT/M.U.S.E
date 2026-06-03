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
import androidx.compose.runtime.mutableStateOf
import androidx.core.content.ContextCompat
import com.aci.hermes.data.preferences.ThemeMode
import com.aci.hermes.notify.DeepLink
import com.aci.hermes.service.HermesService
import com.aci.hermes.service.JobNotifier
import com.aci.hermes.ui.navigation.HermesNavHost
import com.aci.hermes.ui.theme.HermesTheme

class MainActivity : ComponentActivity() {

    private val requestNotificationPermission =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) {
            // Service is already running; this just unlocks the user-visible
            // notification on Android 13+. We do not retry on denial.
        }

    // Notification deep-link, set on launch and refreshed by onNewIntent so a
    // tap on a job notification routes to the exact Job Detail / Approvals.
    private val pendingDeepLink = mutableStateOf<JobNotifier.DeepLink?>(null)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        startHermesOrchestrator()
        maybeRequestNotificationPermission()
        pendingDeepLink.value = JobNotifier.parseDeepLink(intent)

        val container = (application as HermesApplication).container

        // A notification tap launches us with a route extra — publish it so
        // HermesNavHost can open the right screen.
        container.requestDeepLink(intent?.getStringExtra(DeepLink.EXTRA_NAV_ROUTE))

        setContent {
            val themePref by container.settingsRepository.themeMode.collectAsState(
                initial = ThemeMode.SYSTEM
            )
            HermesTheme(themeMode = themePref) {
                HermesNavHost(
                    container = container,
                    deepLink = pendingDeepLink.value,
                    onDeepLinkHandled = { pendingDeepLink.value = null },
                )
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        // FLAG_ACTIVITY_SINGLE_TOP delivers a notification tap here when we're
        // already on top; route it the same way as a cold launch.
        setIntent(intent)
        JobNotifier.parseDeepLink(intent)?.let { pendingDeepLink.value = it }
    }

    override fun onResume() {
        super.onResume()
        (application as HermesApplication).container.onAppForeground()
    }

    override fun onPause() {
        super.onPause()
        (application as HermesApplication).container.onAppBackground()
    }

    private fun startHermesOrchestrator() {
        val intent = Intent(this, HermesService::class.java).apply {
            putExtra(HermesService.EXTRA_LAUNCH_SOURCE, HermesService.DEFAULT_LAUNCH_SOURCE)
            putExtra(HermesService.EXTRA_MODE, HermesService.DEFAULT_MODE)
        }
        ContextCompat.startForegroundService(this, intent)
    }

    private fun maybeRequestNotificationPermission() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) return
        val granted = ContextCompat.checkSelfPermission(
            this,
            Manifest.permission.POST_NOTIFICATIONS,
        ) == PackageManager.PERMISSION_GRANTED
        if (granted) return
        requestNotificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
    }
}
