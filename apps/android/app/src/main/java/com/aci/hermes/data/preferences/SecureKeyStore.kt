package com.aci.hermes.data.preferences

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

/**
 * Wraps [EncryptedSharedPreferences] for storing secrets (gateway token,
 * provider API keys). Keys are sealed with a hardware-backed master key when
 * the device supports it (AES256_GCM aead, AES256_SIV index).
 *
 * Stored values never leave the device; `data_extraction_rules.xml` and
 * `backup_rules.xml` exclude the prefs file from Auto Backup / Device Transfer.
 */
class SecureKeyStore(context: Context) {
    private val prefs: SharedPreferences

    init {
        val masterKey = MasterKey.Builder(context)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()
        prefs = EncryptedSharedPreferences.create(
            context,
            FILE_NAME,
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
        )
    }

    fun put(key: String, value: String?) {
        prefs.edit().apply {
            if (value.isNullOrEmpty()) remove(key) else putString(key, value)
            apply()
        }
    }

    fun get(key: String): String? = prefs.getString(key, null)

    fun clear() {
        prefs.edit().clear().apply()
    }

    companion object {
        const val FILE_NAME = "hermes_secure_prefs"
        const val KEY_GATEWAY_TOKEN = "gateway_token"
        const val KEY_PROVIDER_API_KEY = "provider_api_key"
    }
}
