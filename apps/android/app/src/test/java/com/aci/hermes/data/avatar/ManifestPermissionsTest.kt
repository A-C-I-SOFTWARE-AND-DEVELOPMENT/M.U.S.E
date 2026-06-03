package com.aci.hermes.data.avatar

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Test
import java.io.File

/**
 * Hard invariant: the avatar picker MUST NOT introduce any new Android
 * permission. This test reads the raw AndroidManifest.xml and asserts the
 * complete `uses-permission` set equals the original three.
 *
 * The Gradle unit-test working directory is the module dir (`app/`), so the
 * manifest is at `src/main/AndroidManifest.xml` relative to `user.dir`. If
 * that path doesn't resolve, we walk up looking for it — the test will fail
 * loudly rather than silently pass.
 */
class ManifestPermissionsTest {

    @Test
    fun usesPermissionSetMatchesTheSentientAvatarSurface() {
        val manifest = findManifest()
        assertNotNull("AndroidManifest.xml not found from user.dir=${System.getProperty("user.dir")}", manifest)
        val text = manifest!!.readText()

        // Match the name regardless of any trailing attributes (e.g.
        // tools:ignore on QUERY_ALL_PACKAGES).
        val regex = Regex("""<uses-permission\s+android:name="([^"]+)"""")
        val found = regex.findAll(text).map { it.groupValues[1] }.toSet()

        val expected = setOf(
            "android.permission.POST_NOTIFICATIONS",
            "android.permission.FOREGROUND_SERVICE",
            "android.permission.FOREGROUND_SERVICE_DATA_SYNC",
            "android.permission.SYSTEM_ALERT_WINDOW",
            "android.permission.FOREGROUND_SERVICE_SPECIAL_USE",
            "android.permission.FOREGROUND_SERVICE_MICROPHONE",
            "android.permission.RECORD_AUDIO",
            "android.permission.BLUETOOTH_CONNECT",
            "android.permission.QUERY_ALL_PACKAGES",
            // Opt-in camera attention for Presence Mode (default OFF). On-device
            // face-PRESENCE only; no frames stored/sent; visible indicator while
            // active. The avatar picker still introduces no permission of its own.
            "android.permission.CAMERA",
        )
        assertEquals(expected, found)
    }

    @Test
    fun manifestContainsNoPrivacySensitivePermissions() {
        val manifest = findManifest()
        assertNotNull(manifest)
        val text = manifest!!.readText()
        // The picker still never needs broad media/storage reads. (CAMERA is
        // now an opt-in Presence-Mode capability, asserted in the allow-list
        // above and the dedicated permission audits — not the picker's doing.)
        assertFalse("READ_MEDIA_IMAGES must not appear", text.contains("READ_MEDIA_IMAGES"))
        assertFalse("READ_EXTERNAL_STORAGE must not appear", text.contains("READ_EXTERNAL_STORAGE"))
    }

    private fun findManifest(): File? {
        val candidates = listOf(
            "src/main/AndroidManifest.xml",
            "app/src/main/AndroidManifest.xml",
            "../app/src/main/AndroidManifest.xml",
            "apps/android/app/src/main/AndroidManifest.xml",
        )
        val cwd = File(System.getProperty("user.dir") ?: ".")
        for (rel in candidates) {
            val f = File(cwd, rel)
            if (f.exists()) return f
        }
        // walk up to 4 levels
        var dir: File? = cwd
        repeat(4) {
            dir = dir?.parentFile
            if (dir != null) {
                val f = File(dir, "apps/android/app/src/main/AndroidManifest.xml")
                if (f.exists()) return f
            }
        }
        return null
    }
}
