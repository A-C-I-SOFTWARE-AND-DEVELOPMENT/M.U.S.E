package com.aci.hermes.data.devicecontrol

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.provider.Settings
import androidx.core.content.ContextCompat
import com.aci.hermes.data.automation.AppTargetResolver
import com.aci.hermes.data.automation.AutomationIntent
import com.aci.hermes.data.automation.JarvisChoreographer
import com.aci.hermes.data.automation.ResolvedTarget
import com.aci.hermes.data.automation.ScreenPoint
import com.aci.hermes.data.emergency.EmergencyStopController
import com.aci.hermes.data.preferences.SettingsRepository
import com.aci.hermes.service.JarvisAccessibilityService
import com.aci.hermes.service.JarvisOverlayService
import com.aci.hermes.service.VoiceLoopService
import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.launchIn
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.onEach
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

/**
 * The Android-facing brain of mobile-native device control. It is the
 * "overlay wiring layer" the voice loop and accessibility service were
 * built to call into:
 *
 *  - holds the owner's consent (mirrored from [SettingsRepository]),
 *  - reads live OS grant status for each capability,
 *  - routes every device action through the pure [DeviceActionBroker],
 *  - records every outcome to the [DeviceActionLedger],
 *  - projects the global [EmergencyStopController] halt onto device control
 *    and feeds the accessibility service's `gestureGuard` so any engaged
 *    stop — from any surface — drops gestures mid-flight.
 *
 * It never bypasses the broker, and it executes only what the broker
 * approves. Sensitive actions that need confirmation are logged and
 * refused on the voice path — the owner confirms them deliberately from
 * the Device control screen, never silently.
 *
 * The emergency halt is **not** a local flag the controller can flip: it is
 * a read-only projection of [EmergencyStopController.state]. So there is no
 * device-local "release" that could silently disagree with the audited
 * global stop, and the halt survives a process restart (the stop state is
 * persisted) instead of resetting to false. The only path back to running
 * is the replay-protected `requestResume` → `approveResume` on the global
 * controller.
 */
class DeviceControlController(
    private val context: Context,
    private val settings: SettingsRepository,
    private val ledger: DeviceActionLedger,
    private val logBuffer: LogBuffer,
    private val emergencyStop: EmergencyStopController,
    private val clock: () -> Long = System::currentTimeMillis,
    private val idGenerator: () -> String = { java.util.UUID.randomUUID().toString() },
    private val scope: CoroutineScope = CoroutineScope(SupervisorJob() + Dispatchers.Default),
) {

    @Volatile
    private var consent: DeviceConsentState = DeviceConsentState()

    /**
     * Synchronous mirror of the global stop's active state, read by the
     * (non-suspending) [gesturesAllowed] gate and the broker call. Updated by
     * the [emergencyStop] state collector in [init].
     */
    @Volatile
    private var haltedSnapshot: Boolean = emergencyStop.state.value.isActive

    /**
     * True while any global emergency stop level is engaged. A pure projection
     * of [EmergencyStopController.state] — the controller never writes it.
     */
    val halted: StateFlow<Boolean> = emergencyStop.state
        .map { it.isActive }
        .stateIn(scope, SharingStarted.Eagerly, emergencyStop.state.value.isActive)

    private val _pending = MutableStateFlow<PendingDeviceAction?>(null)
    /**
     * A sensitive action held for explicit owner confirmation. The Device
     * control screen surfaces this with Approve / Dismiss. At most one is
     * outstanding at a time — a newer hold replaces an older one.
     */
    val pending: StateFlow<PendingDeviceAction?> = _pending.asStateFlow()

    /** Recent device actions, newest last — surfaced on the Device control screen. */
    val log: StateFlow<List<DeviceActionLogEntry>> = ledger.entries

    init {
        // Mirror consent into a volatile snapshot so the synchronous
        // gestureGuard and the broker call always see the latest value.
        combine(
            settings.deviceControlEnabled,
            settings.deviceConfirmSensitive,
            settings.deviceConsentedCapabilities,
        ) { enabled, confirm, capIds ->
            DeviceConsentState(
                enabled = enabled,
                consentedCapabilities = capIds.mapNotNull(DeviceControlCapability::fromId).toSet(),
                confirmSensitiveActions = confirm,
            )
        }.onEach { consent = it }.launchIn(scope)

        scope.launch { ledger.load() }

        // Project the global emergency stop onto device control. Any engaged
        // level (SOFT_PAUSE/HARD_STOP/LOCKDOWN), from any surface, flips the
        // synchronous snapshot and — on the rising edge — tears down the
        // overlay + voice loop and records the halt in the device ledger. The
        // controller never sets this false; only the audited global resume can.
        emergencyStop.state
            .map { it.isActive }
            .distinctUntilChanged()
            .onEach { active ->
                haltedSnapshot = active
                if (active) onEmergencyHalt()
            }
            .launchIn(scope)

        // Wire the accessibility service's gesture guard: gestures are only
        // allowed while device control is enabled and not halted. This is the
        // last line of defense — even a stray plan is dropped when halted.
        JarvisAccessibilityService.gestureGuard = { gesturesAllowed() }
    }

    /** Snapshot of the owner's current consent. */
    fun consentState(): DeviceConsentState = consent

    /** Whether the accessibility service may dispatch a gesture right now. */
    fun gesturesAllowed(): Boolean = consent.enabled && !haltedSnapshot

    /** Capabilities the OS currently grants (independent of owner consent). */
    fun grantedCapabilities(): Set<DeviceControlCapability> = buildSet {
        if (JarvisAccessibilityService.isConnected) add(DeviceControlCapability.ACCESSIBILITY)
        if (Settings.canDrawOverlays(context)) add(DeviceControlCapability.OVERLAY)
        if (hasPermission(Manifest.permission.RECORD_AUDIO)) add(DeviceControlCapability.MICROPHONE)
        if (notificationsGranted()) add(DeviceControlCapability.NOTIFICATIONS)
        // QUERY_ALL_PACKAGES is an install-time permission declared in the
        // manifest, so package visibility is always available on this build.
        add(DeviceControlCapability.PACKAGE_VISIBILITY)
        // INTERNET is an install-time permission declared in the manifest
        // (needed to reach the local gateway over loopback), so reaching the
        // backend is a pairing/consent concern surfaced on the Control screen,
        // not a runtime OS grant — the capability is always available.
        add(DeviceControlCapability.BACKEND_CONNECTION)
    }

    // ── Emergency stop projection ───────────────────────────────────────

    /**
     * React to the global emergency stop engaging: drop the floating overlay
     * and the voice loop and record the halt. Driven by the [emergencyStop]
     * state projection in [init], so it fires for a stop engaged from *any*
     * surface — not only the device button — and never sets the halt itself.
     * Releasing is owner-gated on the global controller (`requestResume` →
     * `approveResume`); device control has no local release.
     */
    private fun onEmergencyHalt() {
        runCatching { JarvisOverlayService.stop(context) }
        runCatching { VoiceLoopService.stop(context) }
        logBuffer.warn(TAG, "Device control halted by emergency stop")
        scope.launch {
            ledger.record(
                DeviceActionLogEntry(
                    timestamp = clock(),
                    intentLabel = "Emergency stop",
                    sensitivity = DeviceActionSensitivity.SENSITIVE,
                    outcome = DeviceActionLogEntry.Outcome.BLOCKED,
                    reason = "emergency_stop_engaged",
                ),
            )
        }
    }

    // ── Voice / automation entry point ──────────────────────────────────

    /**
     * The seam [VoiceLoopService.Wiring.performAutomation] calls. Resolves
     * the target, builds a packet, asks the broker, logs the decision, and
     * executes only on approval.
     */
    fun dispatchFromVoice(overlay: JarvisOverlayService, intent: AutomationIntent) {
        scope.launch { dispatch(overlay, intent) }
    }

    private suspend fun dispatch(overlay: JarvisOverlayService, intent: AutomationIntent) {
        val a11y = JarvisAccessibilityService.instance
        val resolved: ResolvedTarget? = when (intent) {
            is AutomationIntent.OpenApp ->
                AppTargetResolver(a11y?.installedApps().orEmpty()).resolve(intent.query)
            is AutomationIntent.PushTarget ->
                a11y?.resolveOnScreen(intent.query)?.let {
                    ResolvedTarget(label = intent.query, bounds = it, packageName = null)
                }
            else -> null
        }

        val packet = DeviceActionPacket.from(intent, resolved?.label)

        // Refuse target-dependent intents we couldn't resolve. Without this,
        // an unmatched "open <app>" / "tap <thing>" would fall through to the
        // choreographer's blind center-screen tap while the ledger claimed the
        // requested action ran. This holds even in high-power mode.
        if (packet.requiresResolvedTarget && resolved == null) {
            ledger.record(
                DeviceActionLogEntry(
                    timestamp = clock(),
                    intentLabel = packet.previewLabel,
                    sensitivity = packet.sensitivity,
                    outcome = DeviceActionLogEntry.Outcome.BLOCKED,
                    reason = "unresolved_target",
                ),
            )
            logBuffer.warn(TAG, "Refused unresolved target: ${packet.previewLabel}")
            return
        }

        val decision = DeviceActionBroker.evaluate(
            packet = packet,
            consent = consent,
            emergencyEngaged = haltedSnapshot,
            grantedCapabilities = grantedCapabilities(),
        )
        ledger.record(DeviceActionBroker.logEntryFor(packet, decision, clock()))

        when (decision) {
            BrokerDecision.Approved -> runPlan(packet, intent, resolved, overlay)
            BrokerDecision.NeedsConfirmation -> {
                // Hold the action and surface it for explicit owner approval
                // on the Device control screen instead of dropping it.
                _pending.value = PendingDeviceAction(
                    id = idGenerator(),
                    intent = intent,
                    resolved = resolved,
                    previewLabel = packet.previewLabel,
                    sensitivity = packet.sensitivity,
                    requestedAt = clock(),
                )
                logBuffer.warn(TAG, "Held for confirmation: ${packet.previewLabel}")
            }
            is BrokerDecision.Blocked ->
                logBuffer.warn(TAG, "Blocked (${decision.reason}): ${packet.previewLabel}")
        }
    }

    /**
     * Approve a held sensitive action. The owner's tap *is* the confirmation,
     * so the broker is re-checked with the confirm gate lifted — but the
     * emergency stop, master switch, and permissions are all re-verified, so a
     * stale approval can never bypass them.
     */
    fun approvePending(id: String) {
        val held = _pending.value ?: return
        if (held.id != id) return
        _pending.value = null
        scope.launch {
            val packet = DeviceActionPacket.from(held.intent, held.resolved?.label)
            val decision = DeviceActionBroker.evaluate(
                packet = packet,
                // The owner's tap is the confirmation: lift the SENSITIVE confirm
                // gate and satisfy the IRREVERSIBLE floor — emergency / master
                // switch / permissions are still re-verified by the broker.
                consent = consent.copy(confirmSensitiveActions = false),
                emergencyEngaged = haltedSnapshot,
                grantedCapabilities = grantedCapabilities(),
                confirmationObtained = true,
            )
            if (decision is BrokerDecision.Approved) {
                ledger.record(DeviceActionBroker.logEntryFor(packet, decision, clock()))
                runPlan(packet, held.intent, held.resolved, JarvisOverlayService.active)
            } else {
                ledger.record(DeviceActionBroker.logEntryFor(packet, decision, clock()))
                logBuffer.warn(TAG, "Pending approval refused ($decision): ${packet.previewLabel}")
            }
        }
    }

    /** Dismiss a held sensitive action without running it (logged). */
    fun dismissPending(id: String) {
        val held = _pending.value ?: return
        if (held.id != id) return
        _pending.value = null
        scope.launch {
            ledger.record(
                DeviceActionLogEntry(
                    timestamp = clock(),
                    intentLabel = held.previewLabel,
                    sensitivity = held.sensitivity,
                    outcome = DeviceActionLogEntry.Outcome.BLOCKED,
                    reason = "dismissed",
                ),
            )
        }
        logBuffer.info(TAG, "Pending action dismissed: ${held.previewLabel}")
    }

    /**
     * Run an approved plan via the floating overlay. The decision/approval is
     * already logged by the caller; this only records the execution outcome.
     */
    private suspend fun runPlan(
        packet: DeviceActionPacket,
        intent: AutomationIntent,
        resolved: ResolvedTarget?,
        overlay: JarvisOverlayService?,
    ) {
        if (overlay == null) {
            ledger.record(
                DeviceActionLogEntry(
                    timestamp = clock(),
                    intentLabel = packet.previewLabel,
                    sensitivity = packet.sensitivity,
                    outcome = DeviceActionLogEntry.Outcome.EXECUTION_FAILED,
                    reason = "overlay_inactive",
                ),
            )
            logBuffer.warn(TAG, "Cannot execute, overlay inactive: ${packet.previewLabel}")
            return
        }
        val plan = JarvisChoreographer(screenMetrics()).choreograph(intent, resolved)
        overlay.execute(plan)
        ledger.record(
            DeviceActionLogEntry(
                timestamp = clock(),
                intentLabel = packet.previewLabel,
                sensitivity = packet.sensitivity,
                outcome = DeviceActionLogEntry.Outcome.EXECUTED,
            ),
        )
        logBuffer.info(TAG, "Executed device action: ${packet.previewLabel}")
    }

    // ── helpers ─────────────────────────────────────────────────────────

    private fun screenMetrics(): JarvisChoreographer.ScreenMetrics {
        val dm = context.resources.displayMetrics
        val w = dm.widthPixels.toFloat()
        val h = dm.heightPixels.toFloat()
        return JarvisChoreographer.ScreenMetrics(
            width = w,
            height = h,
            // Best-effort resting position; only affects run-in duration.
            avatarPosition = ScreenPoint(w * 0.12f, h * 0.4f),
        )
    }

    private fun hasPermission(permission: String): Boolean =
        ContextCompat.checkSelfPermission(context, permission) == PackageManager.PERMISSION_GRANTED

    private fun notificationsGranted(): Boolean =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            hasPermission(Manifest.permission.POST_NOTIFICATIONS)
        } else {
            true
        }

    companion object {
        const val TAG = "DeviceControl"
    }
}
