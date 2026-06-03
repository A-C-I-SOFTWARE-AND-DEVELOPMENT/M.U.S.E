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
import com.aci.hermes.data.preferences.SettingsRepository
import com.aci.hermes.service.JarvisAccessibilityService
import com.aci.hermes.service.JarvisOverlayService
import com.aci.hermes.service.VoiceLoopService
import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.launchIn
import kotlinx.coroutines.flow.onEach
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
 *  - owns the device-control emergency halt and feeds the accessibility
 *    service's `gestureGuard` so a halt drops gestures mid-flight.
 *
 * It never bypasses the broker, and it executes only what the broker
 * approves. Sensitive actions that need confirmation are logged and
 * refused on the voice path — the owner confirms them deliberately from
 * the Device control screen, never silently.
 */
class DeviceControlController(
    private val context: Context,
    private val settings: SettingsRepository,
    private val ledger: DeviceActionLedger,
    private val logBuffer: LogBuffer,
    private val clock: () -> Long = System::currentTimeMillis,
    private val scope: CoroutineScope = CoroutineScope(SupervisorJob() + Dispatchers.Default),
) {

    @Volatile
    private var consent: DeviceConsentState = DeviceConsentState()

    private val _halted = MutableStateFlow(false)
    /** True while the device-control emergency stop is engaged. */
    val halted: StateFlow<Boolean> = _halted.asStateFlow()

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

        // Wire the accessibility service's gesture guard: gestures are only
        // allowed while device control is enabled and not halted. This is the
        // last line of defense — even a stray plan is dropped when halted.
        JarvisAccessibilityService.gestureGuard = { gesturesAllowed() }
    }

    /** Snapshot of the owner's current consent. */
    fun consentState(): DeviceConsentState = consent

    /** Whether the accessibility service may dispatch a gesture right now. */
    fun gesturesAllowed(): Boolean = consent.enabled && !_halted.value

    /** Capabilities the OS currently grants (independent of owner consent). */
    fun grantedCapabilities(): Set<DeviceControlCapability> = buildSet {
        if (JarvisAccessibilityService.isConnected) add(DeviceControlCapability.ACCESSIBILITY)
        if (Settings.canDrawOverlays(context)) add(DeviceControlCapability.OVERLAY)
        if (hasPermission(Manifest.permission.RECORD_AUDIO)) add(DeviceControlCapability.MICROPHONE)
        if (notificationsGranted()) add(DeviceControlCapability.NOTIFICATIONS)
        // QUERY_ALL_PACKAGES is an install-time permission declared in the
        // manifest, so package visibility is always available on this build.
        add(DeviceControlCapability.PACKAGE_VISIBILITY)
        // The INTERNET permission is install-time too; reaching the local
        // backend is a pairing/consent concern surfaced on the Control
        // screen, not an OS grant — so the capability is always available.
        add(DeviceControlCapability.BACKEND_CONNECTION)
    }

    // ── Emergency stop ──────────────────────────────────────────────────

    /**
     * Halt device control immediately: drop the gesture guard, stop the
     * floating overlay and the voice loop, and record the halt. Called by
     * the global emergency stop so one tap stands the whole agent down.
     */
    fun engageEmergencyStop() {
        _halted.value = true
        runCatching { JarvisOverlayService.stop(context) }
        runCatching { VoiceLoopService.stop(context) }
        logBuffer.warn(TAG, "Device control emergency stop engaged")
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

    /** Release the device-control halt (the owner resumes deliberately). */
    fun releaseEmergencyStop() {
        _halted.value = false
        logBuffer.info(TAG, "Device control emergency stop released")
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
            emergencyEngaged = _halted.value,
            grantedCapabilities = grantedCapabilities(),
        )
        ledger.record(DeviceActionBroker.logEntryFor(packet, decision, clock()))

        when (decision) {
            BrokerDecision.Approved -> {
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
            BrokerDecision.NeedsConfirmation ->
                logBuffer.warn(TAG, "Held for confirmation: ${packet.previewLabel}")
            is BrokerDecision.Blocked ->
                logBuffer.warn(TAG, "Blocked (${decision.reason}): ${packet.previewLabel}")
        }
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
