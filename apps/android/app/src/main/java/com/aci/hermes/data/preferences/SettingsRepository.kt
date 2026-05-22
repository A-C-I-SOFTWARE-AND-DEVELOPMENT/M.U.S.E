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
 * Non-sensitive user settings (connection mode, gateway URL, provider id,
 * model, theme, onboarding flag). Secrets — provider API key, gateway
 * bearer token — live in [SecureKeyStore].
 *
 * `mockMode` (legacy boolean) is still surfaced for backward-compat with
 * older builds, but the canonical signal is now `connectionMode`. The two
 * are kept in sync on write.
 */
class SettingsRepository(
    private val context: Context,
    private val secureKeyStore: SecureKeyStore,
    private val defaultGatewayUrl: String,
    private val defaultMockMode: Boolean
) {
    private object Keys {
        val CONNECTION_MODE = stringPreferencesKey("connection_mode")
        val GATEWAY_URL = stringPreferencesKey("gateway_url")
        val CUSTOM_API_BASE_URL = stringPreferencesKey("custom_api_base_url")
        val PROVIDER_ID = stringPreferencesKey("provider_id")
        val MODEL = stringPreferencesKey("model")
        val LAST_WORKING_MODEL = stringPreferencesKey("last_working_model")
        val THEME_MODE = stringPreferencesKey("theme_mode")
        val MOCK_MODE = booleanPreferencesKey("mock_mode") // legacy, kept in sync
        val ONBOARDED = booleanPreferencesKey("onboarded")
    }

    private val defaultMode: ConnectionMode =
        if (defaultMockMode) ConnectionMode.MOCK else ConnectionMode.DIRECT

    val connectionMode: Flow<ConnectionMode> = context.dataStore.data.map { prefs ->
        prefs[Keys.CONNECTION_MODE]?.let { runCatching { ConnectionMode.valueOf(it) }.getOrNull() }
            ?: legacyModeFrom(prefs)
            ?: defaultMode
    }

    val gatewayUrl: Flow<String> = context.dataStore.data.map {
        it[Keys.GATEWAY_URL] ?: defaultGatewayUrl
    }

    /**
     * Direct mode custom OpenAI-compatible base URL. Used only when
     * `providerId == "custom"`. Separate from `gatewayUrl` so switching
     * between Direct/custom and Hermes-gateway doesn't trample either
     * field.
     *
     * Legacy installs reused `gateway_url` for the custom direct endpoint;
     * if `custom_api_base_url` is unset we fall back to that value so
     * existing users don't have to re-enter it.
     */
    val customApiBaseUrl: Flow<String> = context.dataStore.data.map { prefs ->
        prefs[Keys.CUSTOM_API_BASE_URL]
            ?: prefs[Keys.GATEWAY_URL]?.takeIf { prefs[Keys.PROVIDER_ID] == "custom" }
            ?: ""
    }

    val providerId: Flow<String> = context.dataStore.data.map {
        it[Keys.PROVIDER_ID] ?: "openrouter"
    }

    val model: Flow<String> = context.dataStore.data.map {
        it[Keys.MODEL] ?: DEFAULT_DIRECT_MODEL
    }

    val lastWorkingModel: Flow<String?> = context.dataStore.data.map {
        it[Keys.LAST_WORKING_MODEL]
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

    suspend fun setConnectionMode(mode: ConnectionMode) {
        context.dataStore.edit {
            it[Keys.CONNECTION_MODE] = mode.name
            it[Keys.MOCK_MODE] = (mode == ConnectionMode.MOCK)
        }
    }

    suspend fun setGatewayUrl(url: String) {
        context.dataStore.edit { it[Keys.GATEWAY_URL] = url.trim() }
    }

    suspend fun setCustomApiBaseUrl(url: String) {
        context.dataStore.edit { it[Keys.CUSTOM_API_BASE_URL] = url.trim() }
    }

    suspend fun setProviderId(id: String) {
        context.dataStore.edit { it[Keys.PROVIDER_ID] = id }
    }

    suspend fun setModel(model: String) {
        context.dataStore.edit { it[Keys.MODEL] = model.trim() }
    }

    suspend fun setLastWorkingModel(model: String) {
        context.dataStore.edit { it[Keys.LAST_WORKING_MODEL] = model.trim() }
    }

    suspend fun setThemeMode(mode: ThemeMode) {
        context.dataStore.edit { it[Keys.THEME_MODE] = mode.name }
    }

    suspend fun setOnboarded(value: Boolean) {
        context.dataStore.edit { it[Keys.ONBOARDED] = value }
    }

    suspend fun gatewayToken(): String? = secureKeyStore.get(SecureKeyStore.KEY_GATEWAY_TOKEN)
    suspend fun setGatewayToken(value: String?) = secureKeyStore.put(SecureKeyStore.KEY_GATEWAY_TOKEN, value)
    suspend fun providerApiKey(): String? = secureKeyStore.get(SecureKeyStore.KEY_PROVIDER_API_KEY)
    suspend fun setProviderApiKey(value: String?) = secureKeyStore.put(SecureKeyStore.KEY_PROVIDER_API_KEY, value)

    suspend fun resetAll() {
        context.dataStore.edit { it.clear() }
        secureKeyStore.clear()
    }

    suspend fun secretsSnapshot(): SecretsSnapshot = SecretsSnapshot(
        gatewayToken = gatewayToken(),
        providerApiKey = providerApiKey()
    )

    data class SecretsSnapshot(
        val gatewayToken: String?,
        val providerApiKey: String?
    )

    suspend fun snapshot(): Snapshot {
        val data = context.dataStore.data.first()
        val mode = data[Keys.CONNECTION_MODE]
            ?.let { runCatching { ConnectionMode.valueOf(it) }.getOrNull() }
            ?: legacyModeFrom(data)
            ?: defaultMode
        val providerId = data[Keys.PROVIDER_ID] ?: "openrouter"
        val customBase = data[Keys.CUSTOM_API_BASE_URL]
            ?: data[Keys.GATEWAY_URL]?.takeIf { providerId == "custom" }
            ?: ""
        return Snapshot(
            connectionMode = mode,
            gatewayUrl = data[Keys.GATEWAY_URL] ?: defaultGatewayUrl,
            customApiBaseUrl = customBase,
            providerId = providerId,
            model = data[Keys.MODEL] ?: DEFAULT_DIRECT_MODEL,
            lastWorkingModel = data[Keys.LAST_WORKING_MODEL],
            themeMode = when (data[Keys.THEME_MODE]) {
                "LIGHT" -> ThemeMode.LIGHT
                "DARK" -> ThemeMode.DARK
                else -> ThemeMode.SYSTEM
            },
            hasOnboarded = data[Keys.ONBOARDED] ?: false
        )
    }

    data class Snapshot(
        val connectionMode: ConnectionMode,
        val gatewayUrl: String,
        val customApiBaseUrl: String,
        val providerId: String,
        val model: String,
        val lastWorkingModel: String?,
        val themeMode: ThemeMode,
        val hasOnboarded: Boolean
    )

    /**
     * Best-effort fallback for installs that pre-date the
     * `connection_mode` key. If the legacy `mock_mode` boolean is set
     * to true we honour it; otherwise we can't disambiguate Direct from
     * Hermes from the legacy state, so return null and let the default
     * apply.
     */
    private fun legacyModeFrom(prefs: Preferences): ConnectionMode? {
        val legacyMockMode = prefs[Keys.MOCK_MODE] ?: return null
        return if (legacyMockMode) ConnectionMode.MOCK else null
    }

    companion object {
        const val DEFAULT_DIRECT_MODEL = "openai/gpt-4o-mini"
    }
}
