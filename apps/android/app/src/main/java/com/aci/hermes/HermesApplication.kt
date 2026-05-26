package com.aci.hermes

import android.app.Application
import com.aci.hermes.di.AppContainer
import com.aci.hermes.service.HermesService

/**
 * Application class for Jarvis Prime.
 *
 * Package name is kept as `com.aci.hermes` so existing installs upgrade
 * cleanly. User-facing identity is Jarvis Prime — see strings.xml.
 */
class HermesApplication : Application() {
    lateinit var container: AppContainer
        private set

    override fun onCreate() {
        super.onCreate()
        container = AppContainer(this)
        // Channels are cheap to create; doing it eagerly means the
        // first time we ever post a notification (after user opt-in)
        // the channel is already there.
        HermesService.ensureNotificationChannel(this)
    }
}
