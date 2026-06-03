package com.aci.hermes

import android.app.Application
import app.rive.runtime.kotlin.core.Rive
import com.aci.hermes.di.AppContainer
import com.aci.hermes.service.HermesService

class HermesApplication : Application() {
    lateinit var container: AppContainer
        private set

    override fun onCreate() {
        super.onCreate()
        container = AppContainer(this)
        // Make sure the orchestrator notification channel exists before
        // MainActivity asks for the POST_NOTIFICATIONS permission.
        HermesService.ensureNotificationChannel(this)
        // Rive runtime for the top-tier animated avatar (no-op if unused).
        runCatching { Rive.init(this) }
    }
}
