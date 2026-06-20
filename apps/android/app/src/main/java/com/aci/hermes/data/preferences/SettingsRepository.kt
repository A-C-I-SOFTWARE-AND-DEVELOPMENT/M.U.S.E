package com.aci.hermes.data.preferences

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.longPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.core.stringSetPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import com.aci.hermes.data.jarvis.AutonomyMode
import com.aci.hermes.data.jarvis.ResponseLength
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.launch

private val Context.dataStore: DataStore<Preferences> by preferencesDataStore(name = "hermes_settings")

/**
 * Local-only orchestrator preferences.
 *
 * Non-sensitive preferences live in DataStore. The one secret the app
 * holds — the cockpit bearer token — does **not** live here in plaintext:
 * it is stored encrypted-at-rest via [SecureTokenStore]
 * ([EncryptedPrefsSecureTokenStore] in production). Provider API keys
 * never reach the phone at all (see the mobile backend contract). A fresh
 * install with a legacy plaintext token is migrated once, on construction,
 * by [CockpitTokenMigration]; the plaintext copy is removed afterwards.
 *
 * Every muse control surface (Control screen, Home dashboard,
 * settings panel) reads through this repository. Defaults are chosen
 * so a fresh install matches the safety floor: lockdown off, approvals
 * required, safety gates on, local-only mode on, mock mode off.
 */
class SettingsRepository(
    private val context: Context,
    // Injectable DataStore seam (mirrors AvatarRepository) so tests pass an
    // isolated store instead of the process-wide singleton. Production keeps
    // the singleton default.
    private val store: DataStore<Preferences> = context.dataStore,
    private val secureTokenStore: SecureTokenStore = EncryptedPrefsSecureTokenStore(context),
    private val scope: CoroutineScope = CoroutineScope(SupervisorJob() + Dispatchers.IO),
) {

    private object Keys {
        val THEME_MODE = stringPreferencesKey("theme_mode")
        val ONBOARDED = booleanPreferencesKey("onboarded")

        val PREFERRED_BUILDER = stringPreferencesKey("preferred_builder")
        val PREFERRED_REVIEWER = stringPreferencesKey("preferred_reviewer")
        val USE_API_KEYS = booleanPreferencesKey("use_api_keys")
        val LOCAL_ONLY_MODE = booleanPreferencesKey("local_only_mode")
        val ALLOW_EXTERNAL_APP_OPENING = booleanPreferencesKey("allow_external_app_opening")
        val CLIPBOARD_HANDOFF_ENABLED = booleanPreferencesKey("clipboard_handoff_enabled")
        val SHOW_SAFETY_WARNINGS = booleanPreferencesKey("show_safety_warnings")

        // muse control surface — added during launch
        // stabilization to give the Control screen + Home dashboard
        // a backing store.
        val AUTONOMY_MODE = stringPreferencesKey("autonomy_mode")
        val RESPONSE_LENGTH = stringPreferencesKey("response_length")
        val MOBILE_MODE = booleanPreferencesKey("mobile_mode")
        val NOTIFICATIONS_ENABLED = booleanPreferencesKey("notifications_enabled")
        val NOTIFICATION_POLL_INTERVAL_SECONDS = longPreferencesKey("notification_poll_interval_seconds")
        val VOICE_ENABLED = booleanPreferencesKey("voice_enabled")
        val INTERACTIVE_ICON_ENABLED = booleanPreferencesKey("interactive_icon_enabled")
        val GATEWAY_ENDPOINT = stringPreferencesKey("gateway_endpoint")
        val COCKPIT_TOKEN = stringPreferencesKey("cockpit_token")
        val MOCK_MODE = booleanPreferencesKey("mock_mode")
        val TERMUX_GATEWAY_MODE = booleanPreferencesKey("termux_gateway_mode")
        val APPROVALS_REQUIRED = booleanPreferencesKey("approvals_required")
        val SAFETY_GATES_ENABLED = booleanPreferencesKey("safety_gates_enabled")
        // Android runtime consent (P1-05) — point-of-use prompts for
        // expanded permissions. Defaults off; owner opts in at first use.
        val MIC_CONSENT = booleanPreferencesKey("mic_consent")
        val OVERLAY_CONSENT = booleanPreferencesKey("overlay_consent")
        val ACCESSIBILITY_CONSENT = booleanPreferencesKey("accessibility_consent")
        val PRIVACY_DISCLOSURE_ACK = booleanPreferencesKey("privacy_disclosure_ack")
    }
        // Mobile-native device control — owner consent for letting Jarvis
        // operate the phone. Master switch defaults off; sensitive actions
        // require confirmation until the owner opts into high-power mode.
        val DEVICE_CONTROL_ENABLED = booleanPreferencesKey("device_control_enabled")
        val DEVICE_CONFIRM_SENSITIVE = booleanPreferencesKey("device_confirm_sensitive")
        val DEVICE_CONSENTED_CAPS = stringSetPreferencesKey("device_consented_capabilities")
        val PRESENCE_MODE_ENABLED = booleanPreferencesKey("presence_mode_enabled")
        val CAMERA_ATTENTION_ENABLED = booleanPreferencesKey("camera_attention_enabled")

        // Unified PWA-first shell (docs/mobile/NEXUS_UNIFIED_APP_PLAN.md).
        // Phase-1 opt-in: when on, the app renders the NEXUS PWA in
        // WebViewHostActivity instead of the native Compose UI. Defaults OFF
        // so the shipped app is unchanged until the owner-gated Phase-2 cutover.
        val UNIFIED_PWA_SHELL_ENABLED = booleanPreferencesKey("unified_pwa_shell_enabled")
    }

    val themeMode: Flow<ThemeMode> = store.data.map {
        when (it[Keys.THEME_MODE]) {
            "LIGHT" -> ThemeMode.LIGHT
            "DARK" -> ThemeMode.DARK
            else -> ThemeMode.SYSTEM
        }
    }

    val hasOnboarded: Flow<Boolean> = store.data.map {
        it[Keys.ONBOARDED] ?: false
    }

    val preferredBuilder: Flow<PreferredBuilder> = store.data.map {
        runCatching { PreferredBuilder.valueOf(it[Keys.PREFERRED_BUILDER] ?: "") }
            .getOrDefault(PreferredBuilder.CODEX)
    }

    val preferredReviewer: Flow<PreferredReviewer> = store.data.map {
        runCatching { PreferredReviewer.valueOf(it[Keys.PREFERRED_REVIEWER] ?: "") }
            .getOrDefault(PreferredReviewer.CLAUDE_CODE)
    }

    val useApiKeys: Flow<Boolean> = store.data.map { it[Keys.USE_API_KEYS] ?: false }
    val localOnlyMode: Flow<Boolean> = store.data.map { it[Keys.LOCAL_ONLY_MODE] ?: true }
    val allowExternalAppOpening: Flow<Boolean> = store.data.map {
        it[Keys.ALLOW_EXTERNAL_APP_OPENING] ?: false
    }
    val clipboardHandoffEnabled: Flow<Boolean> = store.data.map {
        it[Keys.CLIPBOARD_HANDOFF_ENABLED] ?: true
    }
    val showSafetyWarnings: Flow<Boolean> = store.data.map {
        it[Keys.SHOW_SAFETY_WARNINGS] ?: true
    }

    val autonomyMode: Flow<AutonomyMode> = store.data.map {
        AutonomyMode.fromName(it[Keys.AUTONOMY_MODE])
    }

    val responseLength: Flow<ResponseLength> = store.data.map {
        ResponseLength.fromName(it[Keys.RESPONSE_LENGTH])
    }

    val mobileMode: Flow<Boolean> = store.data.map { it[Keys.MOBILE_MODE] ?: true }
    val notificationsEnabled: Flow<Boolean> = store.data.map { it[Keys.NOTIFICATIONS_ENABLED] ?: true }

    /**
     * How often the work watcher polls the cockpit for long-running-work
     * state changes, in seconds. User-configurable; clamped by the watcher
     * service to a sane floor/ceiling. Default is a calm 20s.
     */
    val notificationPollIntervalSeconds: Flow<Long> = store.data.map {
        it[Keys.NOTIFICATION_POLL_INTERVAL_SECONDS] ?: DEFAULT_POLL_INTERVAL_SECONDS
    }
    val voiceEnabled: Flow<Boolean> = store.data.map { it[Keys.VOICE_ENABLED] ?: false }
    val interactiveIconEnabled: Flow<Boolean> = store.data.map {
        it[Keys.INTERACTIVE_ICON_ENABLED] ?: true
    }
    val gatewayEndpoint: Flow<String> = store.data.map {
        it[Keys.GATEWAY_ENDPOINT] ?: DEFAULT_GATEWAY_ENDPOINT
    }
    /**
     * The cockpit bearer token paired with a Hermes gateway (printed by
     * `hermes cockpit serve` / `hermes cockpit token`). This is the
     * **only** secret the cockpit stores — provider API keys never reach
     * the app (contract §intro). Null/blank means "not paired"; the chat
     * + cockpit client stay on their offline-safe paths until set.
     *
     * Backed by the encrypted [secureTokenStore], **not** DataStore. The
     * StateFlow is seeded from the encrypted store at construction and
     * updated by [setCockpitToken] / [clearCockpitToken] and the one-time
     * legacy migration in `init`.
     */
    private val _cockpitToken: MutableStateFlow<String?> =
        MutableStateFlow(runCatching { secureTokenStore.read() }.getOrNull())
    val cockpitToken: StateFlow<String?> = _cockpitToken.asStateFlow()

    init {
        // One-time migration of any legacy plaintext token into the
        // encrypted store, then strip the plaintext copy. Runs off the
        // main thread; the resulting value (if any) is published on
        // [cockpitToken] so live subscribers (AppContainer) pick it up.
        scope.launch {
            val migrated = CockpitTokenMigration.migrate(
                secure = secureTokenStore,
                readLegacy = { store.data.first()[Keys.COCKPIT_TOKEN] },
                clearLegacy = { store.edit { it.remove(Keys.COCKPIT_TOKEN) } },
            )
            if (migrated != null) _cockpitToken.value = migrated
        }
    }

    val mockMode: Flow<Boolean> = store.data.map { it[Keys.MOCK_MODE] ?: false }
    val termuxGatewayMode: Flow<Boolean> = store.data.map { it[Keys.TERMUX_GATEWAY_MODE] ?: false }
    val approvalsRequired: Flow<Boolean> = store.data.map { it[Keys.APPROVALS_REQUIRED] ?: true }
    val safetyGatesEnabled: Flow<Boolean> = store.data.map { it[Keys.SAFETY_GATES_ENABLED] ?: true }
    val privacyLocalOnlyMemory: Flow<Boolean> = store.data.map {
        it[Keys.PRIVACY_LOCAL_ONLY_MEMORY] ?: true
    }
    val emergencyStopEngaged: Flow<Boolean> = store.data.map {
        it[Keys.EMERGENCY_STOP_ENGAGED] ?: false
    }

    // ── Android runtime consent (P1-05) ─────────────────────────────────
    val micConsent: Flow<Boolean> = store.data.map { it[Keys.MIC_CONSENT] ?: false }
    val overlayConsent: Flow<Boolean> = store.data.map { it[Keys.OVERLAY_CONSENT] ?: false }
    val accessibilityConsent: Flow<Boolean> = store.data.map { it[Keys.ACCESSIBILITY_CONSENT] ?: false }
    val privacyDisclosureAck: Flow<Boolean> = store.data.map { it[Keys.PRIVACY_DISCLOSURE_ACK] ?: false }

    suspend fun setMicConsent(value: Boolean) {
        store.edit { it[Keys.MIC_CONSENT] = value }
    }

    suspend fun setOverlayConsent(value: Boolean) {
        store.edit { it[Keys.OVERLAY_CONSENT] = value }
    }

    suspend fun setAccessibilityConsent(value: Boolean) {
        store.edit { it[Keys.ACCESSIBILITY_CONSENT] = value }
    }

    suspend fun setPrivacyDisclosureAck(value: Boolean) {
        store.edit { it[Keys.PRIVACY_DISCLOSURE_ACK] = value }
    }

    /** Hands-free Presence Mode: when on, JARVIS arms the wake word (or the
     * mic-button fallback) so conversation starts without press-and-hold.
     * Default off — the owner opts in. No camera is involved (that is a
     * separate, gated capability).
     */
    val presenceModeEnabled: Flow<Boolean> = store.data.map {
        it[Keys.PRESENCE_MODE_ENABLED] ?: false
    }
    /**
     * Opt-in camera attention for Presence Mode (default off). When on AND
     * Presence Mode is on AND the CAMERA permission is granted, the live
     * screen runs on-device face-presence detection to arm listening when
     * the user looks at the phone. No frames are stored or transmitted; a
     * visible indicator is shown whenever the camera is active.
     */
    val emergencyStopEngaged: Flow<Boolean> = store.data.map {
        it[Keys.EMERGENCY_STOP_ENGAGED] ?: false
    }

    // ── Android runtime consent (P1-05) ─────────────────────────────────
    val micConsent: Flow<Boolean> = store.data.map { it[Keys.MIC_CONSENT] ?: false }
    val overlayConsent: Flow<Boolean> = store.data.map { it[Keys.OVERLAY_CONSENT] ?: false }
    val accessibilityConsent: Flow<Boolean> = store.data.map { it[Keys.ACCESSIBILITY_CONSENT] ?: false }
    val privacyDisclosureAck: Flow<Boolean> = store.data.map { it[Keys.PRIVACY_DISCLOSURE_ACK] ?: false }

    suspend fun setMicConsent(value: Boolean) {
        store.edit { it[Keys.MIC_CONSENT] = value }
    }

    suspend fun setOverlayConsent(value: Boolean) {
        store.edit { it[Keys.OVERLAY_CONSENT] = value }
    }

    suspend fun setAccessibilityConsent(value: Boolean) {
        store.edit { it[Keys.ACCESSIBILITY_CONSENT] = value }
    }

    suspend fun setPrivacyDisclosureAck(value: Boolean) {
        store.edit { it[Keys.PRIVACY_DISCLOSURE_ACK] = value }
    }

    /** Hands-free Presence Mode: when on, JARVIS arms the wake word (or the
     * Opt into the unified PWA-first shell (default off). When on, the app
     * hosts the NEXUS PWA in [com.aci.hermes.ui.web.WebViewHostActivity]
     * instead of the native Compose UI. Off keeps the shipped, native behavior
     * unchanged — the flag is the Phase-1 seam for the owner-gated cutover.
     */
    val unifiedPwaShellEnabled: Flow<Boolean> = store.data.map {
        it[Keys.UNIFIED_PWA_SHELL_ENABLED] ?: false
    }
    /**
     * Alias for [emergencyStopEngaged] used by the Home dashboard. Both
     * names refer to the same persisted value; keeping both lets the
     * Control screen ("engaged" — operator-facing) and the Home
     * dashboard ("active" — banner copy) read through the language
     * each surface uses.
     */
    val emergencyStopActive: Flow<Boolean> get() = emergencyStopEngaged

    // ── Device control consent ─────────────────────────────────────────
    /** Master switch: until on, no device action runs. Defaults off. */
    val emergencyStopEngaged: Flow<Boolean> = store.data.map {
        it[Keys.EMERGENCY_STOP_ENGAGED] ?: false
    }

    // ── Android runtime consent (P1-05) ─────────────────────────────────
    val micConsent: Flow<Boolean> = store.data.map { it[Keys.MIC_CONSENT] ?: false }
    val overlayConsent: Flow<Boolean> = store.data.map { it[Keys.OVERLAY_CONSENT] ?: false }
    val accessibilityConsent: Flow<Boolean> = store.data.map { it[Keys.ACCESSIBILITY_CONSENT] ?: false }
    val privacyDisclosureAck: Flow<Boolean> = store.data.map { it[Keys.PRIVACY_DISCLOSURE_ACK] ?: false }

    suspend fun setMicConsent(value: Boolean) {
        store.edit { it[Keys.MIC_CONSENT] = value }
    }

    suspend fun setOverlayConsent(value: Boolean) {
        store.edit { it[Keys.OVERLAY_CONSENT] = value }
    }

    suspend fun setAccessibilityConsent(value: Boolean) {
        store.edit { it[Keys.ACCESSIBILITY_CONSENT] = value }
    }

    suspend fun setPrivacyDisclosureAck(value: Boolean) {
        store.edit { it[Keys.PRIVACY_DISCLOSURE_ACK] = value }
    }

    /** Hands-free Presence Mode: when on, JARVIS arms the wake word (or the
    val deviceConfirmSensitive: Flow<Boolean> = store.data.map {
        it[Keys.DEVICE_CONFIRM_SENSITIVE] ?: true
    }

    /** The capability ids the owner has explicitly consented to. */
    val deviceConsentedCapabilities: Flow<Set<String>> = store.data.map {
        it[Keys.DEVICE_CONSENTED_CAPS] ?: emptySet()
    }

    suspend fun setThemeMode(mode: ThemeMode) {
        store.edit { it[Keys.THEME_MODE] = mode.name }
    }

    suspend fun setOnboarded(value: Boolean) {
        store.edit { it[Keys.ONBOARDED] = value }
    }

    suspend fun setPreferredBuilder(value: PreferredBuilder) {
        store.edit { it[Keys.PREFERRED_BUILDER] = value.name }
    }

    suspend fun setPreferredReviewer(value: PreferredReviewer) {
        store.edit { it[Keys.PREFERRED_REVIEWER] = value.name }
    }

    suspend fun setUseApiKeys(value: Boolean) {
        store.edit { it[Keys.USE_API_KEYS] = value }
    }

    suspend fun setLocalOnlyMode(value: Boolean) {
        store.edit { it[Keys.LOCAL_ONLY_MODE] = value }
    }

    suspend fun setAllowExternalAppOpening(value: Boolean) {
        store.edit { it[Keys.ALLOW_EXTERNAL_APP_OPENING] = value }
    }

    suspend fun setClipboardHandoffEnabled(value: Boolean) {
        store.edit { it[Keys.CLIPBOARD_HANDOFF_ENABLED] = value }
    }

    suspend fun setShowSafetyWarnings(value: Boolean) {
        store.edit { it[Keys.SHOW_SAFETY_WARNINGS] = value }
    }

    suspend fun setAutonomyMode(value: AutonomyMode) {
        store.edit { it[Keys.AUTONOMY_MODE] = value.name }
    }

    suspend fun setResponseLength(value: ResponseLength) {
        store.edit { it[Keys.RESPONSE_LENGTH] = value.name }
    }

    suspend fun setMobileMode(value: Boolean) {
        store.edit { it[Keys.MOBILE_MODE] = value }
    }

    suspend fun setNotificationsEnabled(value: Boolean) {
        store.edit { it[Keys.NOTIFICATIONS_ENABLED] = value }
    }

    suspend fun setNotificationPollIntervalSeconds(value: Long) {
        store.edit { it[Keys.NOTIFICATION_POLL_INTERVAL_SECONDS] = value }
    }

    suspend fun setVoiceEnabled(value: Boolean) {
        store.edit { it[Keys.VOICE_ENABLED] = value }
    }

    suspend fun setInteractiveIconEnabled(value: Boolean) {
        store.edit { it[Keys.INTERACTIVE_ICON_ENABLED] = value }
    }

    suspend fun setGatewayEndpoint(value: String) {
        store.edit { it[Keys.GATEWAY_ENDPOINT] = value }
    }

    /** Pair the cockpit with a gateway by storing its bearer token (encrypted at rest). */
    suspend fun setCockpitToken(value: String) {
        val trimmed = value.trim()
        secureTokenStore.write(trimmed)
        _cockpitToken.value = trimmed.takeIf { it.isNotBlank() }
    }

    /**
     * Unpair: drop the stored token from the encrypted store *and* remove
     * any legacy plaintext copy (belt-and-suspenders). Chat + cockpit
     * client fall back to their offline-safe paths.
     */
    suspend fun clearCockpitToken() {
        secureTokenStore.clear()
        store.edit { it.remove(Keys.COCKPIT_TOKEN) }
        _cockpitToken.value = null
    }

    suspend fun setMockMode(value: Boolean) {
        store.edit { it[Keys.MOCK_MODE] = value }
    }

    suspend fun setTermuxGatewayMode(value: Boolean) {
        store.edit { it[Keys.TERMUX_GATEWAY_MODE] = value }
    }

    suspend fun setApprovalsRequired(value: Boolean) {
        store.edit { it[Keys.APPROVALS_REQUIRED] = value }
    }

    suspend fun setSafetyGatesEnabled(value: Boolean) {
        store.edit { it[Keys.SAFETY_GATES_ENABLED] = value }
    }

    suspend fun setPrivacyLocalOnlyMemory(value: Boolean) {
        store.edit { it[Keys.PRIVACY_LOCAL_ONLY_MEMORY] = value }
    }

    suspend fun setEmergencyStopEngaged(value: Boolean) {
        store.edit { it[Keys.EMERGENCY_STOP_ENGAGED] = value }
    }

    /** Home-dashboard-friendly alias for [setEmergencyStopEngaged]. */
    suspend fun setEmergencyStopActive(value: Boolean) = setEmergencyStopEngaged(value)

    // ── Device control consent setters ─────────────────────────────────
    suspend fun setDeviceControlEnabled(value: Boolean) {
        store.edit { it[Keys.DEVICE_CONTROL_ENABLED] = value }
    }

    suspend fun setDeviceConfirmSensitive(value: Boolean) {
        store.edit { it[Keys.DEVICE_CONFIRM_SENSITIVE] = value }
    }

    /** Add or remove a capability id from the consented set. */
    suspend fun setCapabilityConsent(capabilityId: String, consented: Boolean) {
        store.edit { prefs ->
            val current = prefs[Keys.DEVICE_CONSENTED_CAPS] ?: emptySet()
            prefs[Keys.DEVICE_CONSENTED_CAPS] =
                if (consented) current + capabilityId else current - capabilityId
        }
    }

    suspend fun setPresenceModeEnabled(value: Boolean) {
        store.edit { it[Keys.PRESENCE_MODE_ENABLED] = value }
    }

    suspend fun setCameraAttentionEnabled(value: Boolean) {
        store.edit { it[Keys.CAMERA_ATTENTION_ENABLED] = value }
    }

    suspend fun setUnifiedPwaShellEnabled(value: Boolean) {
        store.edit { it[Keys.UNIFIED_PWA_SHELL_ENABLED] = value }
    }

    suspend fun resetAll() {
        store.edit { it.clear() }
        secureTokenStore.clear()
        _cockpitToken.value = null
    }

    suspend fun snapshot(): Snapshot {
        val data = store.data.first()
        return Snapshot(
            themeMode = when (data[Keys.THEME_MODE]) {
                "LIGHT" -> ThemeMode.LIGHT
                "DARK" -> ThemeMode.DARK
                else -> ThemeMode.SYSTEM
            },
            hasOnboarded = data[Keys.ONBOARDED] ?: false,
            preferredBuilder = runCatching {
                PreferredBuilder.valueOf(data[Keys.PREFERRED_BUILDER] ?: "")
            }.getOrDefault(PreferredBuilder.CODEX),
            preferredReviewer = runCatching {
                PreferredReviewer.valueOf(data[Keys.PREFERRED_REVIEWER] ?: "")
            }.getOrDefault(PreferredReviewer.CLAUDE_CODE),
            useApiKeys = data[Keys.USE_API_KEYS] ?: false,
            localOnlyMode = data[Keys.LOCAL_ONLY_MODE] ?: true,
            allowExternalAppOpening = data[Keys.ALLOW_EXTERNAL_APP_OPENING] ?: false,
            clipboardHandoffEnabled = data[Keys.CLIPBOARD_HANDOFF_ENABLED] ?: true,
            showSafetyWarnings = data[Keys.SHOW_SAFETY_WARNINGS] ?: true,
            autonomyMode = AutonomyMode.fromName(data[Keys.AUTONOMY_MODE]),
            responseLength = ResponseLength.fromName(data[Keys.RESPONSE_LENGTH]),
            mobileMode = data[Keys.MOBILE_MODE] ?: true,
            notificationsEnabled = data[Keys.NOTIFICATIONS_ENABLED] ?: true,
            voiceEnabled = data[Keys.VOICE_ENABLED] ?: false,
            interactiveIconEnabled = data[Keys.INTERACTIVE_ICON_ENABLED] ?: true,
            gatewayEndpoint = data[Keys.GATEWAY_ENDPOINT] ?: DEFAULT_GATEWAY_ENDPOINT,
            mockMode = data[Keys.MOCK_MODE] ?: false,
            termuxGatewayMode = data[Keys.TERMUX_GATEWAY_MODE] ?: false,
            approvalsRequired = data[Keys.APPROVALS_REQUIRED] ?: true,
            safetyGatesEnabled = data[Keys.SAFETY_GATES_ENABLED] ?: true,
            privacyLocalOnlyMemory = data[Keys.PRIVACY_LOCAL_ONLY_MEMORY] ?: true,
            emergencyStopEngaged = data[Keys.EMERGENCY_STOP_ENGAGED] ?: false,
        )
    }

    data class Snapshot(
        val themeMode: ThemeMode,
        val hasOnboarded: Boolean,
        val preferredBuilder: PreferredBuilder,
        val preferredReviewer: PreferredReviewer,
        val useApiKeys: Boolean,
        val localOnlyMode: Boolean,
        val allowExternalAppOpening: Boolean,
        val clipboardHandoffEnabled: Boolean,
        val showSafetyWarnings: Boolean,
        val autonomyMode: AutonomyMode,
        val responseLength: ResponseLength,
        val mobileMode: Boolean,
        val notificationsEnabled: Boolean,
        val voiceEnabled: Boolean,
        val interactiveIconEnabled: Boolean,
        val gatewayEndpoint: String,
        val mockMode: Boolean,
        val termuxGatewayMode: Boolean,
        val approvalsRequired: Boolean,
        val safetyGatesEnabled: Boolean,
        val privacyLocalOnlyMemory: Boolean,
        val emergencyStopEngaged: Boolean,
    )

    companion object {
        /**
         * Default gateway endpoint for a fresh install — the loopback
         * Hermes gateway port used by the Termux runtime. Blank
         * (`""`) means "unconfigured" and is treated as such by
         * [com.aci.hermes.data.jarvis.JarvisControlProjector]; the
         * default is intentionally non-blank so the Control screen
         * lands on CONNECTED / DISCONNECTED rather than UNCONFIGURED
         * for a fresh install with the Termux gateway running.
         */
        const val DEFAULT_GATEWAY_ENDPOINT: String = "http://127.0.0.1:8765"

        /** Default work-watcher poll cadence (seconds). */
        const val DEFAULT_POLL_INTERVAL_SECONDS: Long = 20L
    }
}

enum class PreferredBuilder { CODEX, CHATGPT, MANUAL }
enum class PreferredReviewer { CLAUDE_CODE, CLAUDE, CHATGPT, MANUAL }
