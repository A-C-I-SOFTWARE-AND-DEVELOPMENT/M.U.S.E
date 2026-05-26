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
 * Jarvis Prime control surfaces (autonomy, approvals, safety gates,
 * emergency stop, gateway endpoint, notifications, voice, interactive
 * icon) live here too so a single DataStore is the source of truth.
 */
class SettingsRepository(private val context: Context) {

    companion object {
        /**
         * Default value for [Snapshot.gatewayEndpoint]. Points at the
         * local Hermes orchestrator on this device — the owner can
         * override with a remote endpoint via the Control surface.
         */
        const val DEFAULT_GATEWAY_ENDPOINT: String = "http://127.0.0.1:8765"
    }

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

        // Jarvis Prime control state. `EMERGENCY_STOP` backs both the
        // `emergencyStopEngaged` (Control surface) and
        // `emergencyStopActive` (Home surface) names — they refer to
        // the same single flag.
        val MOCK_MODE = booleanPreferencesKey("mock_mode")
        val GATEWAY_ENDPOINT = stringPreferencesKey("gateway_endpoint")
        val EMERGENCY_STOP = booleanPreferencesKey("emergency_stop")
        val NOTIFICATIONS_ENABLED = booleanPreferencesKey("notifications_enabled")
        val VOICE_ENABLED = booleanPreferencesKey("voice_enabled")
        val INTERACTIVE_ICON_ENABLED = booleanPreferencesKey("interactive_icon_enabled")
        val AUTONOMY_MODE = stringPreferencesKey("autonomy_mode")
        val APPROVALS_REQUIRED = booleanPreferencesKey("approvals_required")
        val SAFETY_GATES_ENABLED = booleanPreferencesKey("safety_gates_enabled")
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

    /** Jarvis Prime emergency-stop flag, exposed to the Home surface. */
    val emergencyStopActive: Flow<Boolean> = context.dataStore.data.map {
        it[Keys.EMERGENCY_STOP] ?: false
    }

    val autonomyMode: Flow<AutonomyMode> = context.dataStore.data.map {
        runCatching { AutonomyMode.valueOf(it[Keys.AUTONOMY_MODE] ?: "") }
            .getOrDefault(AutonomyMode.MANUAL)
    }

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

    suspend fun setMockMode(value: Boolean) {
        context.dataStore.edit { it[Keys.MOCK_MODE] = value }
    }

    suspend fun setGatewayEndpoint(value: String) {
        context.dataStore.edit { it[Keys.GATEWAY_ENDPOINT] = value }
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

    suspend fun setAutonomyMode(value: AutonomyMode) {
        context.dataStore.edit { it[Keys.AUTONOMY_MODE] = value.name }
    }

    suspend fun setApprovalsRequired(value: Boolean) {
        context.dataStore.edit { it[Keys.APPROVALS_REQUIRED] = value }
    }

    suspend fun setSafetyGatesEnabled(value: Boolean) {
        context.dataStore.edit { it[Keys.SAFETY_GATES_ENABLED] = value }
    }

    /**
     * Control-surface name for the emergency-stop flag. `engaged` and
     * `active` are deliberate synonyms backed by the same DataStore
     * key so callers using either vocabulary stay in sync.
     */
    suspend fun setEmergencyStopEngaged(value: Boolean) {
        context.dataStore.edit { it[Keys.EMERGENCY_STOP] = value }
    }

    /** Home-surface alias for [setEmergencyStopEngaged]. */
    suspend fun setEmergencyStopActive(value: Boolean) = setEmergencyStopEngaged(value)

    suspend fun resetAll() {
        context.dataStore.edit { it.clear() }
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
            mockMode = data[Keys.MOCK_MODE] ?: false,
            gatewayEndpoint = data[Keys.GATEWAY_ENDPOINT] ?: DEFAULT_GATEWAY_ENDPOINT,
            emergencyStopEngaged = data[Keys.EMERGENCY_STOP] ?: false,
            notificationsEnabled = data[Keys.NOTIFICATIONS_ENABLED] ?: true,
            voiceEnabled = data[Keys.VOICE_ENABLED] ?: false,
            interactiveIconEnabled = data[Keys.INTERACTIVE_ICON_ENABLED] ?: true,
            autonomyMode = runCatching {
                AutonomyMode.valueOf(data[Keys.AUTONOMY_MODE] ?: "")
            }.getOrDefault(AutonomyMode.MANUAL),
            approvalsRequired = data[Keys.APPROVALS_REQUIRED] ?: true,
            safetyGatesEnabled = data[Keys.SAFETY_GATES_ENABLED] ?: true,
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
        val mockMode: Boolean = false,
        val gatewayEndpoint: String = DEFAULT_GATEWAY_ENDPOINT,
        val emergencyStopEngaged: Boolean = false,
        val notificationsEnabled: Boolean = true,
        val voiceEnabled: Boolean = false,
        val interactiveIconEnabled: Boolean = true,
        val autonomyMode: AutonomyMode = AutonomyMode.MANUAL,
        val approvalsRequired: Boolean = true,
        val safetyGatesEnabled: Boolean = true,
        val responseLength: ResponseLength = ResponseLength.BALANCED,
        val mobileMode: Boolean = true,
        val termuxGatewayMode: Boolean = false,
        val privacyLocalOnlyMemory: Boolean = true,
    )
}

enum class PreferredBuilder { CODEX, CHATGPT, MANUAL }
enum class PreferredReviewer { CLAUDE_CODE, CLAUDE, CHATGPT, MANUAL }
