package com.aci.hermes

import android.app.Application
import com.aci.hermes.di.AppContainer
import com.aci.hermes.service.HermesService

class HermesApplication : Application() {
    lateinit var container: AppContainer
        private set

    override fun onCreate() {
        super.onCreate()
        container = AppContainer(this)
        // Register the notification channel up-front. Channel creation
        // does not show any user-visible dialog — the system prompt for
        // POST_NOTIFICATIONS is routed through the Jarvis Prime
        // Permission Kernel and only fires after the user has read the
        // education sheet and tapped Continue.
        HermesService.ensureNotificationChannel(this)
    }
}
