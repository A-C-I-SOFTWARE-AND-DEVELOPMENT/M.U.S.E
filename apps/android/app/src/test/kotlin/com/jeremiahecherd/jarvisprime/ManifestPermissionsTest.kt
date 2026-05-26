package com.jeremiahecherd.jarvisprime

import java.io.File
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Verifies the AndroidManifest never opts into permissions we have
 * explicitly ruled out for this onboarding wave.
 *
 * The test reads the manifest text directly so it doesn't need the
 * Android framework to be loaded.
 */
class ManifestPermissionsTest {

    private val manifest: String by lazy {
        val file = File("src/main/AndroidManifest.xml")
        assertTrue("AndroidManifest.xml not found at ${file.absolutePath}", file.exists())
        file.readText()
    }

    @Test
    fun manifestExists() {
        assertNotNull(manifest)
        assertTrue(manifest.contains("<manifest"))
    }

    @Test
    fun noSmsPermissions() {
        val banned = listOf(
            "android.permission.READ_SMS",
            "android.permission.RECEIVE_SMS",
            "android.permission.SEND_SMS",
            "android.permission.RECEIVE_MMS",
            "android.permission.RECEIVE_WAP_PUSH",
        )
        for (perm in banned) {
            assertFalse("SMS permission $perm must not be declared", manifest.contains(perm))
        }
    }

    @Test
    fun noCallLogPermissions() {
        val banned = listOf(
            "android.permission.READ_CALL_LOG",
            "android.permission.WRITE_CALL_LOG",
            "android.permission.PROCESS_OUTGOING_CALLS",
            "android.permission.READ_PHONE_STATE",
        )
        for (perm in banned) {
            assertFalse("Call/Phone permission $perm must not be declared", manifest.contains(perm))
        }
    }

    @Test
    fun noOverlayPermissionInThisWave() {
        assertFalse(
            "SYSTEM_ALERT_WINDOW must not be declared in this onboarding wave",
            manifest.contains("android.permission.SYSTEM_ALERT_WINDOW"),
        )
    }
}
