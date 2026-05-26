package com.aci.hermes.manifest

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import java.io.File

/**
 * Manifest assertions for the Jarvis Prime launch candidate.
 *
 * Jarvis Prime ships with the smallest possible permission surface
 * for a local foreground orchestrator:
 *
 *   - POST_NOTIFICATIONS  (Android 13+ runtime-gated, for the
 *     foreground-service notification)
 *   - FOREGROUND_SERVICE   (declares the foreground service)
 *   - FOREGROUND_SERVICE_DATA_SYNC  (foreground service type)
 *
 * Anything beyond this list is a launch blocker and must be removed
 * before this test re-enters CI. The forbidden list below covers the
 * sensitive permissions that Jarvis Prime is explicitly NOT allowed
 * to request — see the launch task brief.
 */
class ManifestPermissionsTest {

    private val allowedPermissions: Set<String> = setOf(
        "android.permission.POST_NOTIFICATIONS",
        "android.permission.FOREGROUND_SERVICE",
        "android.permission.FOREGROUND_SERVICE_DATA_SYNC",
    )

    private val forbiddenPermissions: Set<String> = setOf(
        "android.permission.RECORD_AUDIO",
        "android.permission.SYSTEM_ALERT_WINDOW",
        "android.permission.READ_SMS",
        "android.permission.SEND_SMS",
        "android.permission.RECEIVE_SMS",
        "android.permission.READ_CONTACTS",
        "android.permission.WRITE_CONTACTS",
        "android.permission.READ_CALL_LOG",
        "android.permission.WRITE_CALL_LOG",
        "android.permission.PROCESS_OUTGOING_CALLS",
        "android.permission.READ_PHONE_STATE",
        "android.permission.CAMERA",
        "android.permission.ACCESS_FINE_LOCATION",
        "android.permission.ACCESS_COARSE_LOCATION",
        "android.permission.ACCESS_BACKGROUND_LOCATION",
        "android.permission.READ_EXTERNAL_STORAGE",
        "android.permission.WRITE_EXTERNAL_STORAGE",
        "android.permission.MANAGE_EXTERNAL_STORAGE",
    )

    @Test
    fun `manifest declares exactly the allowed permission set`() {
        val manifest = readXml("src/main/AndroidManifest.xml")
        val declared = permissionNames(manifest)
        assertEquals(
            "Manifest permissions must match the Jarvis Prime launch allow-list",
            allowedPermissions,
            declared,
        )
    }

    @Test
    fun `manifest never requests a forbidden permission`() {
        val manifest = readXml("src/main/AndroidManifest.xml")
        val declared = permissionNames(manifest)
        for (forbidden in forbiddenPermissions) {
            assertFalse(
                "Forbidden permission must not appear in manifest: $forbidden",
                declared.contains(forbidden),
            )
        }
    }

    @Test
    fun `manifest preserves the com_aci_hermes application name`() {
        val manifest = readXml("src/main/AndroidManifest.xml")
        assertTrue(
            "Application name must be .HermesApplication (relative to com.aci.hermes)",
            manifest.contains("android:name=\".HermesApplication\""),
        )
        assertTrue(
            "Application must use @string/app_name (Jarvis Prime is set in strings.xml)",
            manifest.contains("android:label=\"@string/app_name\""),
        )
    }

    @Test
    fun `emergency stop is reachable from the orchestrator service controller`() {
        // Compile-time pin: if emergencyStop disappears, the global
        // emergency-stop button on every shell destination breaks.
        val method = com.aci.hermes.service.OrchestratorServiceController::class.java.declaredMethods
            .firstOrNull { it.name == "emergencyStop" }
        assertNotNull(
            "OrchestratorServiceController.emergencyStop() must exist on the launch surface",
            method,
        )
    }

    private fun permissionNames(manifest: String): Set<String> {
        // Match every <uses-permission android:name="..." /> entry.
        val regex = Regex("""<uses-permission[^>]*android:name="([^"]+)"""")
        return regex.findAll(manifest).map { it.groupValues[1] }.toSet()
    }

    private fun readXml(relativePath: String): String {
        val direct = File(relativePath)
        if (direct.isFile) return direct.readText()
        val startCwd: String = System.getProperty("user.dir") ?: "."
        var here: File? = File(startCwd)
        while (here != null) {
            val candidate = File(here, "apps/android/app/$relativePath")
            if (candidate.isFile) return candidate.readText()
            val fallback = File(here, relativePath)
            if (fallback.isFile) return fallback.readText()
            here = here.parentFile
        }
        fail("Could not locate $relativePath relative to cwd $startCwd")
        return ""
    }
}
