package com.aci.hermes.ui.screens.control

import android.app.ActivityManager
import android.app.Application
import android.content.Context
import android.content.Intent
import androidx.core.content.ContextCompat
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.aci.hermes.data.jarvis.AuditShortcut
import com.aci.hermes.data.jarvis.AutonomyCapabilities
import com.aci.hermes.data.jarvis.AutonomyMode
import com.aci.hermes.data.jarvis.ConnectedService
import com.aci.hermes.data.jarvis.ControlWarnings
import com.aci.hermes.data.jarvis.JarvisControlProjector
import com.aci.hermes.data.jarvis.JarvisControlState
import com.aci.hermes.data.jarvis.MemoryShortcut
import com.aci.hermes.data.jarvis.PendingWarning
import com.aci.hermes.data.jarvis.WarningLevel
import com.aci.hermes.data.preferences.SettingsRepository
import com.aci.hermes.service.HermesService
import com.aci.hermes.util.LogBuffer
import com.aci.hermes.data.cockpit.CockpitResult
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

class ControlViewModel(
    application: Application,
    private val settings: SettingsRepository,
    private val logBuffer: LogBuffer,
    private val cockpitClient: com.aci.hermes.data.cockpit.HermesCockpitClient? = null,
) : AndroidViewModel(application) {

    private val _state = MutableStateFlow(JarvisControlState())
    val state: StateFlow<JarvisControlState> = _state.asStateFlow()

    init {
        refresh()
    }

    fun refresh() {
        viewModelScope.launch {
            val snap = settings.snapshot()
            val running = isServiceRunning(getApplication(), HermesService::class.java)
            // Real runtime status: reachable iff the cockpit health probe succeeds;
            // connected services are the live detected worker lanes (Codex/Claude).
            // Falls back to honest "disconnected" placeholders when unpaired.
            var reachable = snap.mockMode
            var services = placeholderServices()
            val client = cockpitClient
            if (client != null) {
                reachable = client.health() is CockpitResult.Success
                val workers = client.runtimeWorkers()
                if (workers is CockpitResult.Success) {
                    services = buildList {
                        add(ConnectedService("runtime", "Hermes runtime", reachable))
                        workers.value.workers.forEach {
                            add(ConnectedService(it.id, it.displayName, it.available))
                        }
                    }
                }
            }
            var projected = JarvisControlProjector.project(
                snapshot = snap,
                serviceRunning = running,
                gatewayReachable = reachable,
                connectedServices = services,
                audit = AuditShortcut(recentEvents = 0, lastEventLabel = null),
                memory = MemoryShortcut(savedFacts = 0, lastNote = null),
            )
            // Reconcile autonomy from the backend policy engine so the screen
            // shows the live level, its workspace scope, and the capability
            // list (from approval_policy.capabilities()) — never a local guess.
            if (client != null) {
                when (val autonomy = client.autonomyGet()) {
                    is CockpitResult.Success -> {
                        val s = autonomy.value
                        projected = projected.copy(
                            autonomy = AutonomyMode.fromWire(s.level),
                            codingWorkspaceRoot = s.workspaceRoot,
                            autonomyCapabilities = AutonomyCapabilities(
                                autoApproved = s.capabilities.autoApproved,
                                requiresApproval = s.capabilities.requiresApproval,
                                alwaysDeny = s.capabilities.alwaysDeny,
                                workspaceScoped = s.capabilities.workspaceScoped,
                            ),
                        )
                    }
                    else -> Unit // keep the local projection when unreachable
                }
            }
            _state.value = projected
        }
    }

    // ─── Autonomy ─────────────────────────────────────────────────────

    fun requestAutonomyMode(mode: AutonomyMode) {
        val current = _state.value.autonomy
        if (mode == current) return
        val level = ControlWarnings.levelFor(ControlWarnings.Action.AutonomyChange(current, mode))
        if (level == WarningLevel.NONE) {
            commitAutonomy(mode)
        } else {
            _state.update {
                it.copy(
                    pendingWarning = PendingWarning(
                        level = level,
                        title = "Change autonomy to ${mode.displayName}?",
                        message = mode.summary,
                        confirmLabel = "Switch to ${mode.displayName}",
                        action = ControlWarnings.Action.AutonomyChange(current, mode),
                    ),
                )
            }
        }
    }

    /** Owner-set the approved workspace that High-Autonomy Coding is scoped to. */
    fun setCodingWorkspaceRoot(path: String) {
        _state.update { it.copy(codingWorkspaceRoot = path) }
    }

    /** Instantly drop autonomy back to Assisted (clears any backend latch). */
    fun revokeAutonomy() {
        commitAutonomy(AutonomyMode.ASSISTED)
    }

    private fun commitAutonomy(mode: AutonomyMode) {
        _state.update { it.copy(autonomy = mode, pendingWarning = null) }
        viewModelScope.launch {
            settings.setAutonomyMode(mode)
            logBuffer.info(TAG, "Autonomy mode set to ${mode.name}")
            // Push the level to the backend policy engine so the same gate
            // governs CLI / gateway / worker execution. Best-effort: an
            // unreachable gateway leaves the local preference in place.
            val client = cockpitClient
            if (client != null) {
                val workspace = _state.value.codingWorkspaceRoot
                val result = if (mode.isHighAutonomyCoding) {
                    client.autonomySet(mode.wireValue, workspacePath = workspace)
                } else {
                    client.autonomySet(mode.wireValue)
                }
                if (result is CockpitResult.Success) {
                    val s = result.value
                    _state.update {
                        it.copy(
                            codingWorkspaceRoot = s.workspaceRoot,
                            autonomyCapabilities = AutonomyCapabilities(
                                autoApproved = s.capabilities.autoApproved,
                                requiresApproval = s.capabilities.requiresApproval,
                                alwaysDeny = s.capabilities.alwaysDeny,
                                workspaceScoped = s.capabilities.workspaceScoped,
                            ),
                        )
                    }
                } else {
                    logBuffer.warn(TAG, "Backend autonomy set failed: $result")
                }
            }
            if (mode == AutonomyMode.LOCKDOWN) {
                stopServiceInternal(reason = "lockdown")
            }
        }
    }

    // ─── Approvals & safety gates ─────────────────────────────────────

    fun requestApprovalsRequired(value: Boolean) {
        val action = if (value) ControlWarnings.Action.EnableApprovals
        else ControlWarnings.Action.DisableApprovals
        val level = ControlWarnings.levelFor(action)
        if (level == WarningLevel.NONE) {
            commitApprovals(value)
        } else {
            _state.update {
                it.copy(
                    pendingWarning = PendingWarning(
                        level = level,
                        title = "Disable owner approvals?",
                        message = "Jarvis will run multi-step work without asking first. " +
                            "Destructive steps still need explicit owner consent in the moment.",
                        confirmLabel = "Disable approvals",
                        action = action,
                    ),
                )
            }
        }
    }

    private fun commitApprovals(value: Boolean) {
        _state.update { it.copy(approvalsRequired = value, pendingWarning = null) }
        viewModelScope.launch {
            settings.setApprovalsRequired(value)
            logBuffer.warn(TAG, "Approvals required = $value")
        }
    }

    fun requestSafetyGatesEnabled(value: Boolean) {
        val action = if (value) ControlWarnings.Action.EnableSafetyGates
        else ControlWarnings.Action.DisableSafetyGates
        val level = ControlWarnings.levelFor(action)
        if (level == WarningLevel.NONE) {
            commitSafetyGates(value)
        } else {
            _state.update {
                it.copy(
                    pendingWarning = PendingWarning(
                        level = level,
                        title = "Disable safety gates?",
                        message = "Verification gates are the rails that keep Jarvis owner-loyal. " +
                            "Turning them off is a critical change and is not reversible " +
                            "without a fresh owner confirmation.",
                        confirmLabel = "Disable safety gates",
                        action = action,
                    ),
                )
            }
        }
    }

    private fun commitSafetyGates(value: Boolean) {
        _state.update { it.copy(safetyGatesEnabled = value, pendingWarning = null) }
        viewModelScope.launch {
            settings.setSafetyGatesEnabled(value)
            logBuffer.warn(TAG, "Safety gates enabled = $value")
        }
    }

    // ─── Emergency stop ───────────────────────────────────────────────

    fun requestEmergencyStop() {
        val level = ControlWarnings.levelFor(ControlWarnings.Action.EmergencyStop)
        _state.update {
            it.copy(
                pendingWarning = PendingWarning(
                    level = level,
                    title = "Emergency stop?",
                    message = "Jarvis Prime will halt the orchestrator service and " +
                        "decline any further outbound action until you release the stop. " +
                        "Pending tasks stay saved.",
                    confirmLabel = "Engage emergency stop",
                    action = ControlWarnings.Action.EmergencyStop,
                ),
            )
        }
    }

    /**
     * Engage emergency stop directly (the host screen already confirmed). Runs
     * the same local + backend stop as the warning-dialog path.
     */
    fun emergencyStopNow() {
        commitEmergencyStop()
    }

    fun releaseEmergencyStop() {
        _state.update { it.copy(emergencyStopEngaged = false, pendingWarning = null) }
        viewModelScope.launch {
            settings.setEmergencyStopEngaged(false)
            logBuffer.info(TAG, "Emergency stop released")
        }
    }

    private fun commitEmergencyStop() {
        _state.update {
            it.copy(emergencyStopEngaged = true, jarvisRunning = false, pendingWarning = null)
        }
        viewModelScope.launch {
            settings.setEmergencyStopEngaged(true)
            stopServiceInternal(reason = "emergency_stop")
            // Cancel active backend jobs/workers and drop the policy level to a
            // safe floor. Best-effort: a local stop still applies if unreachable.
            val client = cockpitClient
            if (client != null) {
                when (val res = client.emergencyStop(reason = "owner emergency stop")) {
                    is CockpitResult.Success -> {
                        logBuffer.warn(
                            TAG,
                            "Emergency stop cancelled ${res.value.cancelledCount} job(s); " +
                                "autonomy dropped to ${res.value.autonomyLevel}",
                        )
                        _state.update { it.copy(autonomy = AutonomyMode.fromWire(res.value.autonomyLevel)) }
                    }
                    else -> logBuffer.warn(TAG, "Backend emergency stop unreachable: $res")
                }
            }
            logBuffer.warn(TAG, "Emergency stop engaged by owner")
        }
    }

    // ─── Pending warning dispatch ─────────────────────────────────────

    fun confirmPendingWarning() {
        val pending = _state.value.pendingWarning ?: return
        when (val action = pending.action) {
            is ControlWarnings.Action.AutonomyChange -> commitAutonomy(action.to)
            ControlWarnings.Action.DisableApprovals -> commitApprovals(false)
            ControlWarnings.Action.EnableApprovals -> commitApprovals(true)
            ControlWarnings.Action.DisableSafetyGates -> commitSafetyGates(false)
            ControlWarnings.Action.EnableSafetyGates -> commitSafetyGates(true)
            ControlWarnings.Action.EmergencyStop -> commitEmergencyStop()
            is ControlWarnings.Action.GatewayEndpointChange -> Unit
            ControlWarnings.Action.ToggleMockMode -> Unit
            ControlWarnings.Action.ToggleTermuxGateway -> Unit
        }
    }

    fun dismissPendingWarning() {
        _state.update { it.copy(pendingWarning = null) }
    }

    // ─── Service control ──────────────────────────────────────────────

    fun startJarvis() {
        if (_state.value.emergencyStopEngaged) return
        val ctx = getApplication<Application>()
        val intent = Intent(ctx, HermesService::class.java).apply {
            putExtra(HermesService.EXTRA_LAUNCH_SOURCE, "control_start")
            putExtra(HermesService.EXTRA_MODE, HermesService.DEFAULT_MODE)
        }
        ContextCompat.startForegroundService(ctx, intent)
        logBuffer.info(TAG, "Jarvis service start requested from control")
        refresh()
    }

    fun stopJarvis() {
        stopServiceInternal(reason = "control_stop")
        refresh()
    }

    private fun stopServiceInternal(reason: String) {
        val ctx = getApplication<Application>()
        ctx.stopService(Intent(ctx, HermesService::class.java))
        logBuffer.info(TAG, "Jarvis service stop requested ($reason)")
    }

    @Suppress("DEPRECATION")
    private fun isServiceRunning(context: Context, cls: Class<*>): Boolean {
        val am = context.getSystemService(Context.ACTIVITY_SERVICE) as? ActivityManager ?: return false
        return am.getRunningServices(Integer.MAX_VALUE).any { it.service.className == cls.name }
    }

    private fun placeholderServices(): List<ConnectedService> = listOf(
        ConnectedService(id = "gateway", displayName = "Hermes gateway", connected = false),
        ConnectedService(id = "termux", displayName = "Termux bridge", connected = false),
        ConnectedService(id = "memory", displayName = "Memory store", connected = true),
    )

    companion object {
        const val TAG = "ControlVm"
    }
}
