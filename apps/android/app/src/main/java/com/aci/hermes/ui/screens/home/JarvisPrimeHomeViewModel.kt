package com.aci.hermes.ui.screens.home

import android.app.ActivityManager
import android.app.Application
import android.content.Context
import android.content.Intent
import android.os.Build
import androidx.core.content.ContextCompat
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.cockpit.CockpitHomeRepository
import com.aci.hermes.data.cockpit.CockpitHomeSnapshot
import com.aci.hermes.data.cockpit.CockpitJobsRepository
import com.aci.hermes.data.cockpit.HomeSync
import com.aci.hermes.data.cockpit.JobStatus
import com.aci.hermes.data.emergency.EmergencyStopController
import com.aci.hermes.data.emergency.EmergencyStopState
import com.aci.hermes.data.jarvis.DeviceCapabilitySummary
import com.aci.hermes.data.jarvis.HomeBackendSync
import com.aci.hermes.data.jarvis.JarvisHomeInputs
import com.aci.hermes.data.jarvis.JarvisHomeState
import com.aci.hermes.data.jarvis.JarvisHomeStateDeriver
import com.aci.hermes.data.jarvis.JarvisPresence
import com.aci.hermes.data.orchestrator.HermesTaskRepository
import com.aci.hermes.data.preferences.SettingsRepository
import com.aci.hermes.service.HermesService
import com.aci.hermes.util.LogBuffer
import com.aci.hermes.voice.VoicePhase
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

/**
 * Home command-center ViewModel. Combines the **local** task/service/
 * settings signals with the **live** cockpit overlay
 * ([CockpitHomeRepository]) and the audited emergency-stop state
 * ([EmergencyStopController]) into one [JarvisHomeState] via the pure
 * [JarvisHomeStateDeriver].
 *
 * Backend reads degrade honestly: an unpaired/unreachable gateway leaves
 * the overlay empty and surfaces a *useful* (never blank) state through
 * [JarvisHomeState.backendSync].
 */
class JarvisPrimeHomeViewModel(
    application: Application,
    private val settings: SettingsRepository,
    private val tasksRepo: HermesTaskRepository,
    private val logBuffer: LogBuffer,
    private val homeRepo: CockpitHomeRepository,
    private val jobsRepo: CockpitJobsRepository,
    private val emergencyController: EmergencyStopController,
) : AndroidViewModel(application) {

    private val serviceRunning = MutableStateFlow(false)
    private val transientPresence = MutableStateFlow<JarvisPresence?>(null)

    private val deviceCapability: DeviceCapabilitySummary = probeDeviceCapability(application)

    val state: StateFlow<JarvisHomeState> = combine(
        combine(
            tasksRepo.tasks,
            settings.localOnlyMode,
            emergencyController.state,
            serviceRunning,
            transientPresence,
        ) { tasks, localOnly, emergency, running, transient ->
            LocalBundle(tasks, localOnly, emergency, running, transient)
        },
        combine(homeRepo.snapshot, homeRepo.sync) { snapshot, sync ->
            BackendBundle(snapshot, sync)
        },
    ) { local, backend ->
        JarvisHomeStateDeriver.derive(
            JarvisHomeInputs(
                serviceRunning = local.serviceRunning,
                tasks = local.tasks,
                localOnlyMode = local.localOnlyMode,
                emergencyStopActive = local.emergency.isActive,
                transientPresence = local.transientPresence,
                cockpit = backend.snapshot,
                backendSync = backend.sync.toHomeSync(),
                backendMessage = (backend.sync as? HomeSync.Error)?.message,
                voicePhase = voicePhaseFor(local.transientPresence),
                deviceCapability = deviceCapability,
            ),
        )
    }.stateIn(viewModelScope, SharingStarted.Eagerly, JarvisHomeState())

    init {
        refreshServiceStatus()
        refreshBackend()
    }

    /** Pull every live cockpit read (launch + pull-to-refresh). */
    fun refreshBackend() {
        viewModelScope.launch { homeRepo.refresh() }
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
        logBuffer.info(HermesService.TAG, "Start requested from muse home")
        refreshServiceStatus()
    }

    /**
     * "Stop all work" / emergency stop. Engages the audited
     * [EmergencyStopController] at HARD_STOP, cancels every non-terminal
     * cockpit job, and stops the foreground service. Each leg is best-effort
     * and independently logged so a failure in one still runs the others.
     */
    fun triggerEmergencyStop() {
        val ctx = getApplication<Application>()
        viewModelScope.launch {
            emergencyController.engage(
                source = "jarvis_home",
                reason = "Stop all work from home",
                target = EmergencyStopState.HARD_STOP,
            )
            cancelRunningJobs()
            ctx.stopService(Intent(ctx, HermesService::class.java))
            logBuffer.warn("JarvisHome", "Emergency stop engaged — work halted")
            refreshServiceStatus()
            refreshBackend()
        }
    }

    /**
     * Deactivate the stop. The owner is physically present at the device, so
     * this performs the request+approve resume in one step — every
     * transition is still written to the emergency-stop audit ledger.
     */
    fun deactivateEmergencyStop() {
        viewModelScope.launch {
            val approval = emergencyController.requestResume(requestedBy = "owner")
            if (approval != null) {
                emergencyController.approveResume(approval.id, approver = "owner")
            }
            logBuffer.info("JarvisHome", "Emergency stop deactivated")
            refreshBackend()
        }
    }

    private suspend fun cancelRunningJobs() {
        val jobs = homeRepo.snapshot.value.jobs?.jobs ?: return
        jobs.filter { JobStatus.fromWire(it.status)?.isTerminal == false }
            .forEach { job ->
                runCatching { jobsRepo.cancel(job.id, reason = "Emergency stop") }
                    .onFailure { logBuffer.warn("JarvisHome", "Cancel ${job.id} failed: ${it.message}") }
            }
    }

    private fun voicePhaseFor(transient: JarvisPresence?): VoicePhase = when (transient) {
        JarvisPresence.LISTENING -> VoicePhase.LISTENING
        JarvisPresence.THINKING -> VoicePhase.THINKING
        else -> VoicePhase.DORMANT
    }

    private fun HomeSync.toHomeSync(): HomeBackendSync = when (this) {
        is HomeSync.Loaded -> HomeBackendSync.LIVE
        is HomeSync.NotPaired -> HomeBackendSync.NOT_PAIRED
        is HomeSync.Error -> HomeBackendSync.OFFLINE
        HomeSync.Idle, HomeSync.Loading -> HomeBackendSync.UNKNOWN
    }

    private fun probeDeviceCapability(ctx: Context): DeviceCapabilitySummary {
        val am = ctx.getSystemService(Context.ACTIVITY_SERVICE) as? ActivityManager
        val mem = ActivityManager.MemoryInfo().also { am?.getMemoryInfo(it) }
        val totalRamMb = (mem.totalMem / (1024 * 1024)).toInt()
        val lowRam = am?.isLowRamDevice ?: false
        val api = Build.VERSION.SDK_INT
        val headline = "${Build.MODEL} · Android API $api"
        val detail = buildString {
            append(if (totalRamMb > 0) "$totalRamMb MB RAM" else "RAM unknown")
            if (lowRam) append(" · low-RAM")
        }
        return DeviceCapabilitySummary(headline = headline, detail = detail)
    }

    @Suppress("DEPRECATION")
    private fun isServiceRunning(context: Context, cls: Class<*>): Boolean {
        val am = context.getSystemService(Context.ACTIVITY_SERVICE) as? ActivityManager ?: return false
        return am.getRunningServices(Integer.MAX_VALUE).any { it.service.className == cls.name }
    }

    private data class LocalBundle(
        val tasks: List<com.aci.hermes.data.model.HermesTask>,
        val localOnlyMode: Boolean,
        val emergency: EmergencyStopState,
        val serviceRunning: Boolean,
        val transientPresence: JarvisPresence?,
    )

    private data class BackendBundle(
        val snapshot: CockpitHomeSnapshot,
        val sync: HomeSync,
    )
}
