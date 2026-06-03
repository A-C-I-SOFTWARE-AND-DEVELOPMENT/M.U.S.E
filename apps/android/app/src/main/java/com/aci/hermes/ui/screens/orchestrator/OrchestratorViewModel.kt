package com.aci.hermes.ui.screens.orchestrator

import android.app.Application
import android.app.ActivityManager
import android.content.Context
import android.content.Intent
import androidx.core.content.ContextCompat
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.cockpit.BackendStatus
import com.aci.hermes.data.cockpit.HermesCockpitClient
import com.aci.hermes.data.model.AiToolProfile
import com.aci.hermes.data.model.DefaultToolProfiles
import com.aci.hermes.data.model.HermesTask
import com.aci.hermes.data.orchestrator.HandoffLauncher
import com.aci.hermes.data.orchestrator.HermesTaskRepository
import com.aci.hermes.data.orchestrator.PromptBuilder
import com.aci.hermes.data.preferences.SettingsRepository
import com.aci.hermes.service.HermesService
import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class OrchestratorUiState(
    val serviceRunning: Boolean = false,
    /**
     * Reachability of the Hermes backend gateway — kept strictly separate
     * from [serviceRunning] (the local foreground service). The local
     * service being up does NOT imply the backend is reachable.
     */
    val backendStatus: BackendStatus = BackendStatus.CHECKING,
    val mode: String = HermesService.DEFAULT_MODE,
    val tools: List<AiToolProfile> = DefaultToolProfiles.all,
    val tasks: List<HermesTask> = emptyList(),
    val allowExternalAppOpening: Boolean = false,
    val clipboardHandoffEnabled: Boolean = true,
    val showSafetyWarnings: Boolean = true,
    val snackbar: String? = null,
)

class OrchestratorViewModel(
    application: Application,
    private val settings: SettingsRepository,
    private val tasksRepo: HermesTaskRepository,
    private val promptBuilder: PromptBuilder,
    private val logBuffer: LogBuffer,
    private val cockpitClient: HermesCockpitClient,
    /** Whether a gateway endpoint is configured (health needs no token). */
    private val endpointConfigured: () -> Boolean = { true },
    private val nowMillis: () -> Long = { System.currentTimeMillis() },
) : AndroidViewModel(application) {

    private val _state = MutableStateFlow(OrchestratorUiState())
    val state: StateFlow<OrchestratorUiState> = _state.asStateFlow()

    // Backend-probe throttling: never re-probe inside the (backoff-scaled)
    // window, and never run two probes at once — so the UI surfaces backend
    // state without ever spamming the gateway.
    private var lastProbeAt = 0L
    private var consecutiveFailures = 0
    private var probeJob: Job? = null

    init {
        probeBackend(force = true)
        viewModelScope.launch {
            tasksRepo.tasks.collect { list ->
                _state.update { it.copy(tasks = list) }
            }
        }
        viewModelScope.launch {
            combine(
                settings.allowExternalAppOpening,
                settings.clipboardHandoffEnabled,
                settings.showSafetyWarnings,
            ) { a, b, c -> Triple(a, b, c) }.collect { (allowExternal, clipboard, warnings) ->
                _state.update {
                    it.copy(
                        allowExternalAppOpening = allowExternal,
                        clipboardHandoffEnabled = clipboard,
                        showSafetyWarnings = warnings,
                    )
                }
            }
        }
        refreshServiceStatus()
    }

    fun refreshServiceStatus() {
        val ctx = getApplication<Application>()
        val running = isServiceRunning(ctx, HermesService::class.java)
        _state.update { it.copy(serviceRunning = running) }
        // Resuming the dashboard is a natural moment to re-check the backend;
        // the interval gate keeps this from turning into a poll.
        probeBackend()
    }

    /**
     * Probe the backend gateway's `/v1/health` and publish a
     * [BackendStatus]. Throttled: skips if a probe ran inside the current
     * (backoff-scaled) window or one is already in flight. [force] (user
     * "Retry" / first launch) bypasses the interval but still coalesces
     * with an in-flight probe.
     */
    fun probeBackend(force: Boolean = false) {
        val now = nowMillis()
        if (!force && now - lastProbeAt < currentIntervalMs()) return
        if (probeJob?.isActive == true) return
        lastProbeAt = now
        // Keep a known-CONNECTED pill steady while we re-check in the
        // background; only show CHECKING when we don't already have a verdict.
        _state.update {
            if (it.backendStatus == BackendStatus.CONNECTED) it
            else it.copy(backendStatus = BackendStatus.CHECKING)
        }
        probeJob = viewModelScope.launch {
            val result = cockpitClient.health()
            val status = BackendStatus.from(endpointConfigured(), result)
            consecutiveFailures =
                if (status == BackendStatus.CONNECTED) 0
                else (consecutiveFailures + 1).coerceAtMost(MAX_BACKOFF_STEPS)
            _state.update { it.copy(backendStatus = status) }
        }
    }

    /** User-initiated retry from the offline banner. */
    fun retryBackend() = probeBackend(force = true)

    /** 20s base, doubling per consecutive failure, capped at 5 minutes. */
    private fun currentIntervalMs(): Long {
        val mult = 1L shl consecutiveFailures.coerceIn(0, MAX_BACKOFF_STEPS)
        return (MIN_PROBE_INTERVAL_MS * mult).coerceAtMost(MAX_PROBE_INTERVAL_MS)
    }

    fun startService() {
        val ctx = getApplication<Application>()
        val intent = Intent(ctx, HermesService::class.java).apply {
            putExtra(HermesService.EXTRA_LAUNCH_SOURCE, "dashboard_start")
            putExtra(HermesService.EXTRA_MODE, HermesService.DEFAULT_MODE)
        }
        ContextCompat.startForegroundService(ctx, intent)
        logBuffer.info(HermesService.TAG, "Service start requested from dashboard")
        refreshServiceStatus()
    }

    fun stopService() {
        val ctx = getApplication<Application>()
        ctx.stopService(Intent(ctx, HermesService::class.java))
        logBuffer.info(HermesService.TAG, "Service stop requested from dashboard")
        refreshServiceStatus()
    }

    fun copyPromptForTask(taskId: String) {
        val task = tasksRepo.byId(taskId) ?: return
        copyPromptForTask(task)
    }

    fun copyPromptForTask(task: HermesTask) {
        val profile = DefaultToolProfiles.byTargetTool(task.targetTool)
        val prompt = promptBuilder.build(task, profile)
        val ok = HandoffLauncher.copyPrompt(
            getApplication(),
            label = "Hermes prompt",
            text = prompt,
        )
        if (ok) {
            _state.update { it.copy(snackbar = "Prompt copied to clipboard") }
            logBuffer.info("Orchestrator", "Copied prompt for task ${task.id}")
        } else {
            _state.update { it.copy(snackbar = "Failed to access clipboard") }
        }
    }

    fun openToolFor(profile: AiToolProfile) {
        val result = HandoffLauncher.openOfficialTool(
            context = getApplication(),
            profile = profile,
            allowExternal = _state.value.allowExternalAppOpening,
        )
        val msg = when (result) {
            is HandoffLauncher.LaunchResult.Opened -> "Opened ${profile.displayName} (${result.via})"
            is HandoffLauncher.LaunchResult.ManualOnly -> result.message
            HandoffLauncher.LaunchResult.Blocked ->
                "External app opening is disabled in Settings → Orchestrator preferences."
        }
        _state.update { it.copy(snackbar = msg) }
    }

    fun consumeSnackbar() {
        _state.update { it.copy(snackbar = null) }
    }

    @Suppress("DEPRECATION")
    private fun isServiceRunning(context: Context, cls: Class<*>): Boolean {
        // ActivityManager.getRunningServices is deprecated for cross-app
        // queries but still works for the caller's own services, which
        // is what we need here.
        val am = context.getSystemService(Context.ACTIVITY_SERVICE) as? ActivityManager ?: return false
        return am.getRunningServices(Integer.MAX_VALUE)
            .any { it.service.className == cls.name }
    }

    private companion object {
        const val MIN_PROBE_INTERVAL_MS = 20_000L
        const val MAX_PROBE_INTERVAL_MS = 300_000L
        const val MAX_BACKOFF_STEPS = 4
    }
}
