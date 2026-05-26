package com.aci.hermes

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * Static guard on the AndroidManifest. Jarvis Prime explicitly refuses
 * to declare SMS, call log, microphone background, or overlay
 * permissions. We assert that the manifest never regresses.
 *
 * The test reads the manifest directly from the source tree so it can
 * run as a plain JVM unit test.
 */
class PermissionManifestTest {

    private val manifest: String = run {
        val candidates = listOf(
            File("src/main/AndroidManifest.xml"),
            File("app/src/main/AndroidManifest.xml"),
            File("apps/android/app/src/main/AndroidManifest.xml"),
        )
        candidates.firstOrNull { it.exists() }?.readText()
            ?: error("could not locate AndroidManifest.xml from ${File(".").absolutePath}")
    }

    @Test
    fun no_sms_permissions() {
        listOf(
            "android.permission.READ_SMS",
            "android.permission.RECEIVE_SMS",
            "android.permission.SEND_SMS",
            "android.permission.WRITE_SMS",
        ).forEach {
            assertFalse("manifest contains $it", manifest.contains(it))
        }
    }

    @Test
    fun no_call_log_permissions() {
        listOf(
            "android.permission.READ_CALL_LOG",
            "android.permission.WRITE_CALL_LOG",
            "android.permission.PROCESS_OUTGOING_CALLS",
        ).forEach {
            assertFalse("manifest contains $it", manifest.contains(it))
        }
    }

    @Test
    fun no_overlay_permission() {
        assertFalse(
            "manifest contains SYSTEM_ALERT_WINDOW",
            manifest.contains("SYSTEM_ALERT_WINDOW"),
        )
    }

    @Test
    fun no_background_microphone_permission() {
        // Jarvis Prime delegates voice to the system SpeechRecognizer
        // intent, which doesn't require the app to hold RECORD_AUDIO.
        assertFalse(
            "manifest unexpectedly contains RECORD_AUDIO",
            manifest.contains("android.permission.RECORD_AUDIO"),
        )
    }

    @Test
    fun no_contacts_permission() {
        assertFalse(manifest.contains("android.permission.READ_CONTACTS"))
        assertFalse(manifest.contains("android.permission.WRITE_CONTACTS"))
    }

    @Test
    fun expected_minimal_permissions_present() {
        assertTrue(manifest.contains("android.permission.POST_NOTIFICATIONS"))
        assertTrue(manifest.contains("android.permission.FOREGROUND_SERVICE"))
    }
}
