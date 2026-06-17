package dev.aci.nexus.daemon.service

import android.content.Context
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

/** Paired M.U.S.E. credentials, held in EncryptedSharedPreferences (same auth as the PWA). */
data class Credentials(val baseUrl: String, val token: String, val pwaHost: String) {
    companion object {
        private const val FILE = "nexus_creds"

        private fun prefs(ctx: Context) = EncryptedSharedPreferences.create(
            ctx,
            FILE,
            MasterKey.Builder(ctx).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build(),
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
        )

        fun load(ctx: Context): Credentials? {
            val p = prefs(ctx)
            val base = p.getString("baseUrl", null) ?: return null
            val token = p.getString("token", null) ?: return null
            val host = p.getString("pwaHost", base) ?: base
            return Credentials(base, token, host)
        }

        fun save(ctx: Context, creds: Credentials) {
            prefs(ctx).edit()
                .putString("baseUrl", creds.baseUrl)
                .putString("token", creds.token)
                .putString("pwaHost", creds.pwaHost)
                .apply()
        }
    }
}
