package com.aci.hermes.data.preferences

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map

private val Context.dataStore: DataStore<Preferences> by preferencesDataStore(name = "hermes_settings")

/**
 * Local-only Jarvis Prime preferences. Provider tokens have never lived
 * here and never will — Jarvis Prime does not call provider APIs from
 * the phone.
 */
class SettingsRepository(private val context: Context) {

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

        // Jarvis Prime additions
        val MOCK_MODE = booleanPreferencesKey("mock_mode")
        val GATEWAY_MODE = stringPreferencesKey("gateway_mode")
        val STATUS_NOTIFICATION_OPT_IN = booleanPreferencesKey("status_notification_opt_in")
        val DOUBLE_CONFIRM_SERIOUS = booleanPreferencesKey("double_confirm_serious")
        val CRITICAL_PHRASE_REQUIRED = booleanPreferencesKey("critical_phrase_required")
        val VOICE_TAP_REQUIRED = booleanPreferencesKey("voice_tap_required")
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

    /** Mock Mode is on by default so the app feels alive without wiring. */
    val mockMode: Flow<Boolean> = context.dataStore.data.map {
        it[Keys.MOCK_MODE] ?: true
    }
    val gatewayMode: Flow<GatewayPreference> = context.dataStore.data.map {
        when (it[Keys.GATEWAY_MODE]) {
            "TERMUX" -> GatewayPreference.TERMUX
            "REMOTE" -> GatewayPreference.REMOTE
            else -> GatewayPreference.MOCK
        }
    }
    val statusNotificationOptIn: Flow<Boolean> = context.dataStore.data.map {
        it[Keys.STATUS_NOTIFICATION_OPT_IN] ?: false
    }
    val doubleConfirmSerious: Flow<Boolean> = context.dataStore.data.map {
        it[Keys.DOUBLE_CONFIRM_SERIOUS] ?: true
    }
    val criticalPhraseRequired: Flow<Boolean> = context.dataStore.data.map {
        it[Keys.CRITICAL_PHRASE_REQUIRED] ?: true
    }
    val voiceTapRequired: Flow<Boolean> = context.dataStore.data.map {
        it[Keys.VOICE_TAP_REQUIRED] ?: true
    }

    suspend fun setThemeMode(mode: ThemeMode) { context.dataStore.edit { it[Keys.THEME_MODE] = mode.name } }
    suspend fun setOnboarded(value: Boolean) { context.dataStore.edit { it[Keys.ONBOARDED] = value } }
    suspend fun setPreferredBuilder(value: PreferredBuilder) { context.dataStore.edit { it[Keys.PREFERRED_BUILDER] = value.name } }
    suspend fun setPreferredReviewer(value: PreferredReviewer) { context.dataStore.edit { it[Keys.PREFERRED_REVIEWER] = value.name } }
    suspend fun setUseApiKeys(value: Boolean) { context.dataStore.edit { it[Keys.USE_API_KEYS] = value } }
    suspend fun setLocalOnlyMode(value: Boolean) { context.dataStore.edit { it[Keys.LOCAL_ONLY_MODE] = value } }
    suspend fun setAllowExternalAppOpening(value: Boolean) { context.dataStore.edit { it[Keys.ALLOW_EXTERNAL_APP_OPENING] = value } }
    suspend fun setClipboardHandoffEnabled(value: Boolean) { context.dataStore.edit { it[Keys.CLIPBOARD_HANDOFF_ENABLED] = value } }
    suspend fun setShowSafetyWarnings(value: Boolean) { context.dataStore.edit { it[Keys.SHOW_SAFETY_WARNINGS] = value } }
    suspend fun setMockMode(value: Boolean) { context.dataStore.edit { it[Keys.MOCK_MODE] = value } }
    suspend fun setGatewayMode(value: GatewayPreference) { context.dataStore.edit { it[Keys.GATEWAY_MODE] = value.name } }
    suspend fun setStatusNotificationOptIn(value: Boolean) { context.dataStore.edit { it[Keys.STATUS_NOTIFICATION_OPT_IN] = value } }
    suspend fun setDoubleConfirmSerious(value: Boolean) { context.dataStore.edit { it[Keys.DOUBLE_CONFIRM_SERIOUS] = value } }
    suspend fun setCriticalPhraseRequired(value: Boolean) { context.dataStore.edit { it[Keys.CRITICAL_PHRASE_REQUIRED] = value } }
    suspend fun setVoiceTapRequired(value: Boolean) { context.dataStore.edit { it[Keys.VOICE_TAP_REQUIRED] = value } }

    suspend fun resetAll() { context.dataStore.edit { it.clear() } }

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
            mockMode = data[Keys.MOCK_MODE] ?: true,
            gatewayMode = when (data[Keys.GATEWAY_MODE]) {
                "TERMUX" -> GatewayPreference.TERMUX
                "REMOTE" -> GatewayPreference.REMOTE
                else -> GatewayPreference.MOCK
            },
            statusNotificationOptIn = data[Keys.STATUS_NOTIFICATION_OPT_IN] ?: false,
            doubleConfirmSerious = data[Keys.DOUBLE_CONFIRM_SERIOUS] ?: true,
            criticalPhraseRequired = data[Keys.CRITICAL_PHRASE_REQUIRED] ?: true,
            voiceTapRequired = data[Keys.VOICE_TAP_REQUIRED] ?: true,
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
        val mockMode: Boolean,
        val gatewayMode: GatewayPreference,
        val statusNotificationOptIn: Boolean,
        val doubleConfirmSerious: Boolean,
        val criticalPhraseRequired: Boolean,
        val voiceTapRequired: Boolean,
    )
}

enum class PreferredBuilder { CODEX, CHATGPT, MANUAL }
enum class PreferredReviewer { CLAUDE_CODE, CLAUDE, CHATGPT, MANUAL }
enum class GatewayPreference { MOCK, TERMUX, REMOTE }
