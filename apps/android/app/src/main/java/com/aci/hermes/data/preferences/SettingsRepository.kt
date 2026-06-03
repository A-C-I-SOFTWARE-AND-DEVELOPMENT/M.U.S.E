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
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map

private val Context.dataStore: DataStore<Preferences> by preferencesDataStore(name = "hermes_settings")

/**
 * Local-only orchestrator preferences. Hermes deliberately does not
 * store any provider API keys or session tokens — the legacy
 * EncryptedSharedPreferences store was removed when Chat / Provider
 * was retired.
 *
 * Every Jarvis Prime control surface (Control screen, Home dashboard,
 * settings panel) reads through this repository. Defaults are chosen
 * so a fresh install matches the safety floor: lockdown off, approvals
 * required, safety gates on, local-only mode on, mock mode off.
 */
class SettingsRepository(
    context: Context,
    // Injectable for tests/isolation, mirroring AvatarRepository. Production
    // keeps the process-wide singleton; tests pass an isolated DataStore so a
    // shared singleton can't leak or go stale across cases.
    private val store: DataStore<Preferences> = context.dataStore,
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
     */
    val cockpitToken: Flow<String?> = store.data.map {
        it[Keys.COCKPIT_TOKEN]?.takeIf { token -> token.isNotBlank() }
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
    /**
     * Alias for [emergencyStopEngaged] used by the Home dashboard. Both
     * names refer to the same persisted value; keeping both lets the
     * Control screen ("engaged" — operator-facing) and the Home
     * dashboard ("active" — banner copy) read through the language
     * each surface uses.
     */
    val emergencyStopActive: Flow<Boolean> get() = emergencyStopEngaged

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

    suspend fun setVoiceEnabled(value: Boolean) {
        store.edit { it[Keys.VOICE_ENABLED] = value }
    }

    suspend fun setInteractiveIconEnabled(value: Boolean) {
        store.edit { it[Keys.INTERACTIVE_ICON_ENABLED] = value }
    }

    suspend fun setGatewayEndpoint(value: String) {
        store.edit { it[Keys.GATEWAY_ENDPOINT] = value }
    }

    /** Pair the cockpit with a gateway by storing its bearer token. */
    suspend fun setCockpitToken(value: String) {
        store.edit { it[Keys.COCKPIT_TOKEN] = value.trim() }
    }

    /** Unpair: drop the stored token (chat + cockpit client fall back to offline-safe). */
    suspend fun clearCockpitToken() {
        store.edit { it.remove(Keys.COCKPIT_TOKEN) }
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

    suspend fun resetAll() {
        store.edit { it.clear() }
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
    }
}

enum class PreferredBuilder { CODEX, CHATGPT, MANUAL }
enum class PreferredReviewer { CLAUDE_CODE, CLAUDE, CHATGPT, MANUAL }
