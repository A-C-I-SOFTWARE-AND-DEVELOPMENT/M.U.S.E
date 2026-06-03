package com.aci.hermes.data.preferences

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

/**
 * Encrypted-at-rest store for the cockpit bearer token.
 *
 * The cockpit bearer token is the only secret the app holds (provider
 * API keys never reach the phone — see the mobile backend contract). It
 * used to live in plaintext DataStore; it now lives here, encrypted with
 * a hardware-backed key. Non-sensitive preferences stay in DataStore.
 *
 * The interface is deliberately tiny so the migration core
 * ([CockpitTokenMigration]) can be unit-tested against an in-memory fake
 * without pulling the Android Keystore into a JVM test.
 */
interface SecureTokenStore {
    /** Return the stored token, or `null` if none is set / readable. */
    fun read(): String?

    /** Persist [token] (trimmed), replacing any existing value. */
    fun write(token: String)

    /** Remove the stored token. */
    fun clear()
}

/**
 * [SecureTokenStore] backed by AndroidX Security Crypto's
 * [EncryptedSharedPreferences] (AES-256 keys, AES-256-SIV key names,
 * AES-256-GCM values; master key in the Android Keystore).
 *
 * Every operation is wrapped in [runCatching] so a Keystore failure
 * (e.g. a device that lost its key material) degrades to "no token"
 * rather than crashing the app — the cockpit simply reads as unpaired
 * and the owner can re-pair.
 */
class EncryptedPrefsSecureTokenStore(
    context: Context,
    private val fileName: String = DEFAULT_FILE,
) : SecureTokenStore {

    private val appContext = context.applicationContext

    private val prefs: SharedPreferences? by lazy {
        runCatching {
            val masterKey = MasterKey.Builder(appContext)
                .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
                .build()
            EncryptedSharedPreferences.create(
                appContext,
                fileName,
                masterKey,
                EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
            )
        }.getOrNull()
    }

    override fun read(): String? =
        runCatching {
            prefs?.getString(KEY_COCKPIT_TOKEN, null)?.takeIf { it.isNotBlank() }
        }.getOrNull()

    override fun write(token: String) {
        runCatching { prefs?.edit()?.putString(KEY_COCKPIT_TOKEN, token.trim())?.apply() }
    }

    override fun clear() {
        runCatching { prefs?.edit()?.remove(KEY_COCKPIT_TOKEN)?.apply() }
    }

    companion object {
        const val DEFAULT_FILE = "hermes_secure_prefs"
        private const val KEY_COCKPIT_TOKEN = "cockpit_token"
    }
}

/**
 * One-time migration of the cockpit bearer token out of legacy plaintext
 * storage and into a [SecureTokenStore].
 *
 * Pure (no Android dependencies) so it can be exercised directly by unit
 * tests — the live [SettingsRepository] path calls exactly this function.
 *
 * Safety: if the secure store already has a token, the legacy value is
 * left untouched and **not** read. If writing to the secure store fails,
 * the legacy plaintext value is preserved (returned) so the owner never
 * loses their pairing — better a still-encrypted-next-launch retry than a
 * lost token.
 */
object CockpitTokenMigration {
    suspend fun migrate(
        secure: SecureTokenStore,
        readLegacy: suspend () -> String?,
        clearLegacy: suspend () -> Unit,
    ): String? {
        val existing = runCatching { secure.read() }.getOrNull()
        if (!existing.isNullOrBlank()) return existing

        val legacy = runCatching { readLegacy() }.getOrNull()?.takeIf { it.isNotBlank() }
            ?: return null

        return runCatching {
            secure.write(legacy)
            clearLegacy()
            legacy
        }.getOrElse {
            // Secure write / legacy clear failed — keep the plaintext value
            // readable so the next launch can retry the migration.
            legacy
        }
    }
}
