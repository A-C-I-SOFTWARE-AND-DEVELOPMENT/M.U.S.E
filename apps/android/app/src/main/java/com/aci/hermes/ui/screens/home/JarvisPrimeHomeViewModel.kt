package com.aci.hermes.ui.screens.home

import android.app.ActivityManager
import android.app.Application
import android.content.Context
import android.content.Intent
import androidx.core.content.ContextCompat
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.jarvis.JarvisHomeInputs
import com.aci.hermes.data.jarvis.JarvisHomeState
import com.aci.hermes.data.jarvis.JarvisHomeStateDeriver
import com.aci.hermes.data.jarvis.JarvisPresence
import com.aci.hermes.data.orchestrator.HermesTaskRepository
import com.aci.hermes.data.preferences.SettingsRepository
import com.aci.hermes.service.HermesService
import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

class JarvisPrimeHomeViewModel(
    application: Application,
    private val settings: SettingsRepository,
    private val tasksRepo: HermesTaskRepository,
    private val logBuffer: LogBuffer,
) : AndroidViewModel(application) {

    private val serviceRunning = MutableStateFlow(false)
    private val transientPresence = MutableStateFlow<JarvisPresence?>(null)

    val state: StateFlow<JarvisHomeState> = combine(
        tasksRepo.tasks,
        settings.localOnlyMode,
        settings.emergencyStopActive,
        serviceRunning,
        transientPresence,
    ) { tasks, localOnly, emergencyStop, running, transient ->
        JarvisHomeStateDeriver.derive(
            JarvisHomeInputs(
                serviceRunning = running,
                tasks = tasks,
                localOnlyMode = localOnly,
                emergencyStopActive = emergencyStop,
                transientPresence = transient,
            )
        )
    }.stateIn(viewModelScope, SharingStarted.Eagerly, JarvisHomeState())

    init {
        refreshServiceStatus()
    }

    fun refreshServiceStatus() {
        val ctx = getApplication<Application>()
        serviceRunning.value = isServiceRunning(ctx, HermesService::class.java)
    }

    fun startListening() {
        transientPresence.value = JarvisPresence.LISTENING
        logBuffer.info("JarvisHome", "Voice listening started")
    }

    fun stopListening() {
        if (transientPresence.value == JarvisPresence.LISTENING) {
            transientPresence.value = null
        }
    }

    fun startThinking() {
        transientPresence.value = JarvisPresence.THINKING
    }

    fun clearTransient() {
        transientPresence.value = null
    }

    fun startService() {
        val ctx = getApplication<Application>()
        val intent = Intent(ctx, HermesService::class.java).apply {
            putExtra(HermesService.EXTRA_LAUNCH_SOURCE, "jarvis_home_start")
            putExtra(HermesService.EXTRA_MODE, HermesService.DEFAULT_MODE)
        }
        ContextCompat.startForegroundService(ctx, intent)
        logBuffer.info(HermesService.TAG, "Start requested from Jarvis home")
        refreshServiceStatus()
    }

    fun triggerEmergencyStop() {
        val ctx = getApplication<Application>()
        viewModelScope.launch {
            settings.setEmergencyStopActive(true)
            ctx.stopService(Intent(ctx, HermesService::class.java))
            logBuffer.warn("JarvisHome", "Emergency stop engaged — service halted")
            refreshServiceStatus()
        }
    }

    fun deactivateEmergencyStop() {
        viewModelScope.launch {
            settings.setEmergencyStopActive(false)
            logBuffer.info("JarvisHome", "Emergency stop deactivated")
        }
    }

    @Suppress("DEPRECATION")
    private fun isServiceRunning(context: Context, cls: Class<*>): Boolean {
        val am = context.getSystemService(Context.ACTIVITY_SERVICE) as? ActivityManager ?: return false
        return am.getRunningServices(Integer.MAX_VALUE).any { it.service.className == cls.name }
    }
}
