package com.jeremiahecherd.jarvisprime

import android.app.Application
import com.jeremiahecherd.jarvisprime.data.SettingsRepository

class JarvisPrimeApp : Application() {
    val settings: SettingsRepository by lazy { SettingsRepository.create(applicationContext) }
}
