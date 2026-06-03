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
        // commit() (synchronous) rather than apply(): the migration only
        // drops the plaintext copy after verifying this landed, so we need
        // the value durable on disk before that happens, not queued async.
        runCatching { prefs?.edit()?.putString(KEY_COCKPIT_TOKEN, token.trim())?.commit() }
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
 * Safety contract — the plaintext copy is removed **only** once the
 * encrypted copy is proven safe:
 *  - The encrypted store fails *soft* (a missing Keystore makes `write()` a
 *    silent no-op, not an exception), so a non-throwing `write()` is not
 *    proof of persistence. We verify by reading the value back; if it did
 *    not land, the plaintext is kept for a next-launch retry.
 *  - If the secure store already holds a token, we still clear any leftover
 *    plaintext copy — a prior run may have persisted the token but failed
 *    to clear DataStore, and that secret must never linger.
 */
object CockpitTokenMigration {
    suspend fun migrate(
        secure: SecureTokenStore,
        readLegacy: suspend () -> String?,
        clearLegacy: suspend () -> Unit,
    ): String? {
        val legacy = runCatching { readLegacy() }.getOrNull()?.takeIf { it.isNotBlank() }

        val existing = runCatching { secure.read() }.getOrNull()?.takeIf { it.isNotBlank() }
        if (existing != null) {
            // Already migrated. Sweep up any plaintext that survived a prior
            // failed clear so it never lingers on disk.
            if (legacy != null) runCatching { clearLegacy() }
            return existing
        }

        if (legacy == null) return null

        // Move plaintext -> encrypted, then VERIFY it persisted before
        // dropping the plaintext. On any failure, keep the plaintext readable
        // so the next launch retries — the owner never loses their pairing.
        val persisted = runCatching {
            secure.write(legacy)
            secure.read() == legacy
        }.getOrDefault(false)

        if (!persisted) return legacy

        runCatching { clearLegacy() }
        return legacy
    }
}
