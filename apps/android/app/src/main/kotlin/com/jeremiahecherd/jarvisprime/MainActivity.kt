package com.jeremiahecherd.jarvisprime

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import com.jeremiahecherd.jarvisprime.nav.JarvisPrimeNavGraph
import com.jeremiahecherd.jarvisprime.ui.theme.JarvisPrimeTheme

/**
 * Launcher activity.
 *
 * Permission policy enforced here (see
 * docs/jarvis-prime-app-permission-flow.md):
 *
 *  - Never call `requestPermissions(...)` from onCreate or any other
 *    lifecycle callback. Notifications, microphone, and overlay all
 *    require an explicit user tap inside an education card first.
 *  - The notification runtime prompt lives in
 *    [com.jeremiahecherd.jarvisprime.ui.onboarding.NotificationEducationScreen]
 *    and is only launched after `onMarkOptedIn` records the user's tap.
 *  - The microphone runtime prompt lives in
 *    [com.jeremiahecherd.jarvisprime.ui.onboarding.VoiceEducationScreen]
 *    and is only launched after `onMarkOptedIn` records the user's tap.
 *  - SYSTEM_ALERT_WINDOW (overlay), READ_SMS, RECEIVE_SMS, SEND_SMS,
 *    READ_CALL_LOG and WRITE_CALL_LOG are NOT requested anywhere in
 *    this wave and are NOT declared in AndroidManifest.xml.
 */
class MainActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val settings = (application as JarvisPrimeApp).settings
        setContent {
            JarvisPrimeTheme {
                JarvisPrimeNavGraph(settings = settings)
            }
        }
    }
}
