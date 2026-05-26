package com.aci.hermes

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import com.aci.hermes.data.preferences.ThemeMode
import com.aci.hermes.ui.navigation.JarvisNavHost
import com.aci.hermes.ui.theme.JarvisTheme

/**
 * Entry activity for Jarvis Prime.
 *
 * Permission-safe by design:
 *  - Notification permission is NOT requested on launch. It is asked
 *    after an in-app education step (see [com.aci.hermes.ui.screens.onboarding.OnboardingScreen]
 *    and [com.aci.hermes.ui.permission.NotificationEducationSheet]).
 *  - Microphone permission is NOT requested on launch. It is asked
 *    only when the user taps voice capture.
 *  - The foreground service is NOT started on launch. It starts after
 *    the user has finished onboarding (or explicitly tapped "Start").
 *  - No overlay, no SMS, no call log.
 */
class MainActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        val container = (application as HermesApplication).container

        setContent {
            val themePref by container.settingsRepository.themeMode.collectAsState(
                initial = ThemeMode.SYSTEM
            )
            JarvisTheme(themeMode = themePref) {
                JarvisNavHost(container = container)
            }
        }
    }
}
