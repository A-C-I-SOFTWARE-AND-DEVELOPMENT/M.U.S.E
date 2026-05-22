package com.aci.hermes.data.preferences

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * Wraps [EncryptedSharedPreferences] for storing secrets (gateway token,
 * provider API keys). Keys are sealed with a hardware-backed master key when
 * the device supports it (AES256_GCM aead, AES256_SIV index).
 *
 * Stored values never leave the device; `data_extraction_rules.xml` and
 * `backup_rules.xml` exclude the prefs file from Auto Backup / Device Transfer.
 *
 * All accessors are `suspend` and hop to `Dispatchers.IO`:
 *   * The MasterKey build + EncryptedSharedPreferences.create() do
 *     Keystore + disk work; on slow OEM keystores the first call has
 *     been observed to ANR if it runs on Main.
 *   * Subsequent reads of an already-loaded `SharedPreferences` are
 *     usually cheap but the *first* read after process start blocks
 *     while the file is parsed and decrypted.
 */
class SecureKeyStore(private val context: Context) {

    @Volatile private var cached: SharedPreferences? = null

    private suspend fun prefs(): SharedPreferences = cached ?: withContext(Dispatchers.IO) {
        cached ?: run {
            val masterKey = MasterKey.Builder(context)
                .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
                .build()
            val created = EncryptedSharedPreferences.create(
                context,
                FILE_NAME,
                masterKey,
                EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
            )
            cached = created
            created
        }
    }

    suspend fun put(key: String, value: String?) = withContext(Dispatchers.IO) {
        val p = prefs()
        p.edit().apply {
            if (value.isNullOrEmpty()) remove(key) else putString(key, value)
            apply()
        }
    }

    suspend fun get(key: String): String? = withContext(Dispatchers.IO) {
        prefs().getString(key, null)
    }

    suspend fun clear() = withContext(Dispatchers.IO) {
        prefs().edit().clear().apply()
    }

    companion object {
        const val FILE_NAME = "hermes_secure_prefs"
        const val KEY_GATEWAY_TOKEN = "gateway_token"
        const val KEY_PROVIDER_API_KEY = "provider_api_key"
    }
}
