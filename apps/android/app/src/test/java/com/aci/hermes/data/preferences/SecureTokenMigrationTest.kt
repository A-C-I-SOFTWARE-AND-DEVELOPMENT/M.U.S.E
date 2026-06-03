package com.aci.hermes.data.preferences

import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * Unit tests for the cockpit-token secure-storage contract:
 *  - the [SecureTokenStore] save / read / clear behaviour, and
 *  - the one-time [CockpitTokenMigration] from legacy plaintext storage.
 *
 * These run on the plain JVM against an in-memory [FakeSecureTokenStore]
 * so the real Android Keystore is never needed — the migration core is
 * pure, and it is the exact function SettingsRepository calls on
 * construction, so this is not a change-detector.
 */
class SecureTokenMigrationTest {

    /** In-memory stand-in for the encrypted store; mirrors its semantics. */
    private class FakeSecureTokenStore(
        private var value: String? = null,
        /** When set, [write] throws — exercises the safe-failure path. */
        var failWrites: Boolean = false,
    ) : SecureTokenStore {
        override fun read(): String? = value?.takeIf { it.isNotBlank() }
        override fun write(token: String) {
            if (failWrites) throw IllegalStateException("keystore unavailable")
            value = token.trim()
        }
        override fun clear() { value = null }
    }

    // --- SecureTokenStore contract ------------------------------------

    @Test
    fun `save then read returns the token`() {
        val store = FakeSecureTokenStore()
        store.write("tok-abc123")
        assertEquals("tok-abc123", store.read())
    }

    @Test
    fun `read returns null when unset`() {
        assertNull(FakeSecureTokenStore().read())
    }

    @Test
    fun `clear removes the token`() {
        val store = FakeSecureTokenStore(value = "tok-abc123")
        store.clear()
        assertNull(store.read())
    }

    @Test
    fun `blank values read back as null`() {
        val store = FakeSecureTokenStore(value = "   ")
        assertNull(store.read())
    }

    // --- Migration ----------------------------------------------------

    @Test
    fun `migration moves a legacy plaintext token into the secure store`() = runTest {
        val secure = FakeSecureTokenStore()
        var legacy: String? = "legacy-token-xyz"

        val result = CockpitTokenMigration.migrate(
            secure = secure,
            readLegacy = { legacy },
            clearLegacy = { legacy = null },
        )

        assertEquals("legacy-token-xyz", result)
        assertEquals("legacy-token-xyz", secure.read())
    }

    @Test
    fun `no plaintext token remains after migration`() = runTest {
        val secure = FakeSecureTokenStore()
        var legacy: String? = "legacy-token-xyz"

        CockpitTokenMigration.migrate(
            secure = secure,
            readLegacy = { legacy },
            clearLegacy = { legacy = null },
        )

        assertNull("legacy plaintext must be cleared", legacy)
    }

    @Test
    fun `migration is a no-op when the secure store already has a token`() = runTest {
        val secure = FakeSecureTokenStore(value = "already-secure")
        var legacy: String? = "stale-plaintext"

        val result = CockpitTokenMigration.migrate(
            secure = secure,
            readLegacy = { legacy },
            clearLegacy = { legacy = null },
        )

        assertEquals("already-secure", result)
        // Legacy left untouched: we never read or clear it once secure wins.
        assertEquals("stale-plaintext", legacy)
    }

    @Test
    fun `migration returns null when there is nothing to migrate`() = runTest {
        val secure = FakeSecureTokenStore()
        val result = CockpitTokenMigration.migrate(
            secure = secure,
            readLegacy = { null },
            clearLegacy = { },
        )
        assertNull(result)
        assertNull(secure.read())
    }

    @Test
    fun `migration preserves the legacy token if the secure write fails`() = runTest {
        val secure = FakeSecureTokenStore(failWrites = true)
        var legacy: String? = "legacy-token-xyz"

        val result = CockpitTokenMigration.migrate(
            secure = secure,
            readLegacy = { legacy },
            clearLegacy = { legacy = null },
        )

        // No data loss: the plaintext value is returned and left in place
        // so a later launch can retry the migration.
        assertEquals("legacy-token-xyz", result)
        assertEquals("legacy-token-xyz", legacy)
        assertNull(secure.read())
    }
}
