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
    fun usesPermissionSetIsExactlyTheOriginalThree() {
        val manifest = findManifest()
        assertNotNull("AndroidManifest.xml not found from user.dir=${System.getProperty("user.dir")}", manifest)
        val text = manifest!!.readText()

        val regex = Regex("""<uses-permission\s+android:name="([^"]+)"\s*/>""")
        val found = regex.findAll(text).map { it.groupValues[1] }.toSet()

        val expected = setOf(
            "android.permission.POST_NOTIFICATIONS",
            "android.permission.FOREGROUND_SERVICE",
            "android.permission.FOREGROUND_SERVICE_DATA_SYNC",
        )
        assertEquals(expected, found)
    }

    @Test
    fun manifestContainsNoPrivacySensitivePermissions() {
        val manifest = findManifest()
        assertNotNull(manifest)
        val text = manifest!!.readText()
        assertFalse("READ_MEDIA_IMAGES must not appear", text.contains("READ_MEDIA_IMAGES"))
        assertFalse("READ_EXTERNAL_STORAGE must not appear", text.contains("READ_EXTERNAL_STORAGE"))
        assertFalse("CAMERA must not appear", text.contains("android.permission.CAMERA"))
        assertFalse("RECORD_AUDIO must not appear", text.contains("RECORD_AUDIO"))
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
