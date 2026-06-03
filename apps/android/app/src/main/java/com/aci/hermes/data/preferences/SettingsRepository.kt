package com.aci.hermes.data.preferences

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
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
 * Every Jarvis Prime control surface (Control screen, Home dashboard,
 * settings panel) reads through this repository. Defaults are chosen
 * so a fresh install matches the safety floor: lockdown off, approvals
 * required, safety gates on, local-only mode on, mock mode off.
 */
class SettingsRepository(
    private val context: Context,
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

        // Jarvis Prime control surface — added during launch
        // stabilization to give the Control screen + Home dashboard
        // a backing store.
        val AUTONOMY_MODE = stringPreferencesKey("autonomy_mode")
        val RESPONSE_LENGTH = stringPreferencesKey("response_length")
        val MOBILE_MODE = booleanPreferencesKey("mobile_mode")
        val NOTIFICATIONS_ENABLED = booleanPreferencesKey("notifications_enabled")
        val VOICE_ENABLED = booleanPreferencesKey("voice_enabled")
        val INTERACTIVE_ICON_ENABLED = booleanPreferencesKey("interactive_icon_enabled")
        val GATEWAY_ENDPOINT = stringPreferencesKey("gateway_endpoint")
        val COCKPIT_TOKEN = stringPreferencesKey("cockpit_token")
        val MOCK_MODE = booleanPreferencesKey("mock_mode")
        val TERMUX_GATEWAY_MODE = booleanPreferencesKey("termux_gateway_mode")
        val APPROVALS_REQUIRED = booleanPreferencesKey("approvals_required")
        val SAFETY_GATES_ENABLED = booleanPreferencesKey("safety_gates_enabled")
        val PRIVACY_LOCAL_ONLY_MEMORY = booleanPreferencesKey("privacy_local_only_memory")
        val EMERGENCY_STOP_ENGAGED = booleanPreferencesKey("emergency_stop_engaged")
    }

    val themeMode: Flow<ThemeMode> = context.dataStore.data.map {
        when (it[Keys.THEME_MODE]) {
            "LIGHT" -> ThemeMode.LIGHT
            "DARK" -> ThemeMode.DARK
            else -> ThemeMode.SYSTEM
        }
    }

    val hasOnboarded: Flow<Boolean> = context.dataStore.data.map {
        it[Keys.ONBOARDED] ?: false
    }

    val preferredBuilder: Flow<PreferredBuilder> = context.dataStore.data.map {
        runCatching { PreferredBuilder.valueOf(it[Keys.PREFERRED_BUILDER] ?: "") }
            .getOrDefault(PreferredBuilder.CODEX)
    }

    val preferredReviewer: Flow<PreferredReviewer> = context.dataStore.data.map {
        runCatching { PreferredReviewer.valueOf(it[Keys.PREFERRED_REVIEWER] ?: "") }
            .getOrDefault(PreferredReviewer.CLAUDE_CODE)
    }

    val useApiKeys: Flow<Boolean> = context.dataStore.data.map { it[Keys.USE_API_KEYS] ?: false }
    val localOnlyMode: Flow<Boolean> = context.dataStore.data.map { it[Keys.LOCAL_ONLY_MODE] ?: true }
    val allowExternalAppOpening: Flow<Boolean> = context.dataStore.data.map {
        it[Keys.ALLOW_EXTERNAL_APP_OPENING] ?: false
    }
    val clipboardHandoffEnabled: Flow<Boolean> = context.dataStore.data.map {
        it[Keys.CLIPBOARD_HANDOFF_ENABLED] ?: true
    }
    val showSafetyWarnings: Flow<Boolean> = context.dataStore.data.map {
        it[Keys.SHOW_SAFETY_WARNINGS] ?: true
    }

    val autonomyMode: Flow<AutonomyMode> = context.dataStore.data.map {
        AutonomyMode.fromName(it[Keys.AUTONOMY_MODE])
    }

    val responseLength: Flow<ResponseLength> = context.dataStore.data.map {
        ResponseLength.fromName(it[Keys.RESPONSE_LENGTH])
    }

    val mobileMode: Flow<Boolean> = context.dataStore.data.map { it[Keys.MOBILE_MODE] ?: true }
    val notificationsEnabled: Flow<Boolean> = context.dataStore.data.map { it[Keys.NOTIFICATIONS_ENABLED] ?: true }
    val voiceEnabled: Flow<Boolean> = context.dataStore.data.map { it[Keys.VOICE_ENABLED] ?: false }
    val interactiveIconEnabled: Flow<Boolean> = context.dataStore.data.map {
        it[Keys.INTERACTIVE_ICON_ENABLED] ?: true
    }
    val gatewayEndpoint: Flow<String> = context.dataStore.data.map {
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
                readLegacy = { context.dataStore.data.first()[Keys.COCKPIT_TOKEN] },
                clearLegacy = { context.dataStore.edit { it.remove(Keys.COCKPIT_TOKEN) } },
            )
            if (migrated != null) _cockpitToken.value = migrated
        }
    }

    val mockMode: Flow<Boolean> = context.dataStore.data.map { it[Keys.MOCK_MODE] ?: false }
    val termuxGatewayMode: Flow<Boolean> = context.dataStore.data.map { it[Keys.TERMUX_GATEWAY_MODE] ?: false }
    val approvalsRequired: Flow<Boolean> = context.dataStore.data.map { it[Keys.APPROVALS_REQUIRED] ?: true }
    val safetyGatesEnabled: Flow<Boolean> = context.dataStore.data.map { it[Keys.SAFETY_GATES_ENABLED] ?: true }
    val privacyLocalOnlyMemory: Flow<Boolean> = context.dataStore.data.map {
        it[Keys.PRIVACY_LOCAL_ONLY_MEMORY] ?: true
    }
    val emergencyStopEngaged: Flow<Boolean> = context.dataStore.data.map {
        it[Keys.EMERGENCY_STOP_ENGAGED] ?: false
    }
    /**
     * Alias for [emergencyStopEngaged] used by the Home dashboard. Both
     * names refer to the same persisted value; keeping both lets the
     * Control screen ("engaged" — operator-facing) and the Home
     * dashboard ("active" — banner copy) read through the language
     * each surface uses.
     */
    val emergencyStopActive: Flow<Boolean> get() = emergencyStopEngaged

    suspend fun setThemeMode(mode: ThemeMode) {
        context.dataStore.edit { it[Keys.THEME_MODE] = mode.name }
    }

    suspend fun setOnboarded(value: Boolean) {
        context.dataStore.edit { it[Keys.ONBOARDED] = value }
    }

    suspend fun setPreferredBuilder(value: PreferredBuilder) {
        context.dataStore.edit { it[Keys.PREFERRED_BUILDER] = value.name }
    }

    suspend fun setPreferredReviewer(value: PreferredReviewer) {
        context.dataStore.edit { it[Keys.PREFERRED_REVIEWER] = value.name }
    }

    suspend fun setUseApiKeys(value: Boolean) {
        context.dataStore.edit { it[Keys.USE_API_KEYS] = value }
    }

    suspend fun setLocalOnlyMode(value: Boolean) {
        context.dataStore.edit { it[Keys.LOCAL_ONLY_MODE] = value }
    }

    suspend fun setAllowExternalAppOpening(value: Boolean) {
        context.dataStore.edit { it[Keys.ALLOW_EXTERNAL_APP_OPENING] = value }
    }

    suspend fun setClipboardHandoffEnabled(value: Boolean) {
        context.dataStore.edit { it[Keys.CLIPBOARD_HANDOFF_ENABLED] = value }
    }

    suspend fun setShowSafetyWarnings(value: Boolean) {
        context.dataStore.edit { it[Keys.SHOW_SAFETY_WARNINGS] = value }
    }

    suspend fun setAutonomyMode(value: AutonomyMode) {
        context.dataStore.edit { it[Keys.AUTONOMY_MODE] = value.name }
    }

    suspend fun setResponseLength(value: ResponseLength) {
        context.dataStore.edit { it[Keys.RESPONSE_LENGTH] = value.name }
    }

    suspend fun setMobileMode(value: Boolean) {
        context.dataStore.edit { it[Keys.MOBILE_MODE] = value }
    }

    suspend fun setNotificationsEnabled(value: Boolean) {
        context.dataStore.edit { it[Keys.NOTIFICATIONS_ENABLED] = value }
    }

    suspend fun setVoiceEnabled(value: Boolean) {
        context.dataStore.edit { it[Keys.VOICE_ENABLED] = value }
    }

    suspend fun setInteractiveIconEnabled(value: Boolean) {
        context.dataStore.edit { it[Keys.INTERACTIVE_ICON_ENABLED] = value }
    }

    suspend fun setGatewayEndpoint(value: String) {
        context.dataStore.edit { it[Keys.GATEWAY_ENDPOINT] = value }
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
        context.dataStore.edit { it.remove(Keys.COCKPIT_TOKEN) }
        _cockpitToken.value = null
    }

    suspend fun setMockMode(value: Boolean) {
        context.dataStore.edit { it[Keys.MOCK_MODE] = value }
    }

    suspend fun setTermuxGatewayMode(value: Boolean) {
        context.dataStore.edit { it[Keys.TERMUX_GATEWAY_MODE] = value }
    }

    suspend fun setApprovalsRequired(value: Boolean) {
        context.dataStore.edit { it[Keys.APPROVALS_REQUIRED] = value }
    }

    suspend fun setSafetyGatesEnabled(value: Boolean) {
        context.dataStore.edit { it[Keys.SAFETY_GATES_ENABLED] = value }
    }

    suspend fun setPrivacyLocalOnlyMemory(value: Boolean) {
        context.dataStore.edit { it[Keys.PRIVACY_LOCAL_ONLY_MEMORY] = value }
    }

    suspend fun setEmergencyStopEngaged(value: Boolean) {
        context.dataStore.edit { it[Keys.EMERGENCY_STOP_ENGAGED] = value }
    }

    /** Home-dashboard-friendly alias for [setEmergencyStopEngaged]. */
    suspend fun setEmergencyStopActive(value: Boolean) = setEmergencyStopEngaged(value)

    suspend fun resetAll() {
        context.dataStore.edit { it.clear() }
        secureTokenStore.clear()
        _cockpitToken.value = null
    }

    suspend fun snapshot(): Snapshot {
        val data = context.dataStore.data.first()
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
    }
}

enum class PreferredBuilder { CODEX, CHATGPT, MANUAL }
enum class PreferredReviewer { CLAUDE_CODE, CLAUDE, CHATGPT, MANUAL }
