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
 * Non-sensitive user settings (gateway URL, theme mode, default provider id,
 * onboarding state, mock mode). API keys and gateway tokens live in
 * [SecureKeyStore] instead.
 */
class SettingsRepository(
    private val context: Context,
    private val secureKeyStore: SecureKeyStore,
    private val defaultGatewayUrl: String,
    private val defaultMockMode: Boolean
) {
    private object Keys {
        val GATEWAY_URL = stringPreferencesKey("gateway_url")
        val PROVIDER_ID = stringPreferencesKey("provider_id")
        val THEME_MODE = stringPreferencesKey("theme_mode")
        val MOCK_MODE = booleanPreferencesKey("mock_mode")
        val ONBOARDED = booleanPreferencesKey("onboarded")
    }

    val gatewayUrl: Flow<String> = context.dataStore.data.map {
        it[Keys.GATEWAY_URL] ?: defaultGatewayUrl
    }

    val providerId: Flow<String> = context.dataStore.data.map {
        it[Keys.PROVIDER_ID] ?: "openrouter"
    }

    val themeMode: Flow<ThemeMode> = context.dataStore.data.map {
        when (it[Keys.THEME_MODE]) {
            "LIGHT" -> ThemeMode.LIGHT
            "DARK" -> ThemeMode.DARK
            else -> ThemeMode.SYSTEM
        }
    }

    val mockMode: Flow<Boolean> = context.dataStore.data.map {
        it[Keys.MOCK_MODE] ?: defaultMockMode
    }

    val hasOnboarded: Flow<Boolean> = context.dataStore.data.map {
        it[Keys.ONBOARDED] ?: false
    }

    suspend fun setGatewayUrl(url: String) {
        context.dataStore.edit { it[Keys.GATEWAY_URL] = url.trim() }
    }

    suspend fun setProviderId(id: String) {
        context.dataStore.edit { it[Keys.PROVIDER_ID] = id }
    }

    suspend fun setThemeMode(mode: ThemeMode) {
        context.dataStore.edit { it[Keys.THEME_MODE] = mode.name }
    }

    suspend fun setMockMode(enabled: Boolean) {
        context.dataStore.edit { it[Keys.MOCK_MODE] = enabled }
    }

    suspend fun setOnboarded(value: Boolean) {
        context.dataStore.edit { it[Keys.ONBOARDED] = value }
    }

    fun gatewayToken(): String? = secureKeyStore.get(SecureKeyStore.KEY_GATEWAY_TOKEN)
    fun setGatewayToken(value: String?) = secureKeyStore.put(SecureKeyStore.KEY_GATEWAY_TOKEN, value)
    fun providerApiKey(): String? = secureKeyStore.get(SecureKeyStore.KEY_PROVIDER_API_KEY)
    fun setProviderApiKey(value: String?) = secureKeyStore.put(SecureKeyStore.KEY_PROVIDER_API_KEY, value)

    suspend fun resetAll() {
        context.dataStore.edit { it.clear() }
        secureKeyStore.clear()
    }

    suspend fun snapshot(): Snapshot {
        val data = context.dataStore.data.first()
        return Snapshot(
            gatewayUrl = data[Keys.GATEWAY_URL] ?: defaultGatewayUrl,
            providerId = data[Keys.PROVIDER_ID] ?: "openrouter",
            themeMode = when (data[Keys.THEME_MODE]) {
                "LIGHT" -> ThemeMode.LIGHT
                "DARK" -> ThemeMode.DARK
                else -> ThemeMode.SYSTEM
            },
            mockMode = data[Keys.MOCK_MODE] ?: defaultMockMode,
            hasOnboarded = data[Keys.ONBOARDED] ?: false
        )
    }

    data class Snapshot(
        val gatewayUrl: String,
        val providerId: String,
        val themeMode: ThemeMode,
        val mockMode: Boolean,
        val hasOnboarded: Boolean
    )
}
