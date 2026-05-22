package com.aci.hermes

import android.app.Application
import com.aci.hermes.di.AppContainer

class HermesApplication : Application() {
    lateinit var container: AppContainer
        private set

    override fun onCreate() {
        super.onCreate()
        container = AppContainer(this)
    }
}
