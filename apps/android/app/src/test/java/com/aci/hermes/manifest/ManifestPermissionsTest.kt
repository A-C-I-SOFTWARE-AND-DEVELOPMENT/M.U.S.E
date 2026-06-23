package com.aci.hermes.manifest

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import java.io.File

/**
 * Manifest assertions for the sentient-avatar build.
 *
 * The original launch candidate shipped the smallest possible surface.
 * The sentient-avatar fork intentionally opts into the power-user
 * permissions the on-screen, device-driving, voice-controlled avatar
 * requires — so this test is **re-baselined** to the new intended set
 * rather than deleted: it still fails loudly if a permission outside
 * the agreed surface sneaks in.
 *
 * Intended surface:
 *   - POST_NOTIFICATIONS / FOREGROUND_SERVICE / *_DATA_SYNC (orchestrator)
 *   - SYSTEM_ALERT_WINDOW            (the avatar floats over other apps)
 *   - FOREGROUND_SERVICE_SPECIAL_USE (overlay presence service)
 *   - FOREGROUND_SERVICE_MICROPHONE + RECORD_AUDIO (headset voice loop)
 *   - BLUETOOTH_CONNECT              (route voice over a headset)
 *   - QUERY_ALL_PACKAGES             (resolve "open Facebook" → package)
 *   - CAMERA                         (opt-in Presence Mode, default OFF)
 *   - INTERNET                       (reach the local gateway over loopback)
 *
 * The forbidden list keeps pinning the permissions the avatar genuinely
 * never needs (SMS, contacts, call log, camera, location, broad storage)
 * so scope creep beyond the avatar's job is still caught.
 */
class ManifestPermissionsTest {

    private val allowedPermissions: Set<String> = setOf(
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
        // active. Everything else camera/contacts/SMS/location/storage stays
        // forbidden below, so scope creep is still caught.
        "android.permission.CAMERA",
        // Reaching the user's own local Hermes gateway (default 127.0.0.1:8765)
        // over loopback/LAN requires INTERNET — Android gates every socket,
        // including localhost, behind it. Used only for the paired local
        // gateway; never for remote AI providers, and no API keys live here.
        "android.permission.INTERNET",
        // In-app "install update": hands the downloaded MUSE APK to the system
        // package installer (visible OS Install/Update dialog). No silent or
        // background install — see data/update/ApkInstaller.
        "android.permission.REQUEST_INSTALL_PACKAGES",
    )

    private val forbiddenPermissions: Set<String> = setOf(
        "android.permission.READ_SMS",
        "android.permission.SEND_SMS",
        "android.permission.RECEIVE_SMS",
        "android.permission.READ_CONTACTS",
        "android.permission.WRITE_CONTACTS",
        "android.permission.READ_CALL_LOG",
        "android.permission.WRITE_CALL_LOG",
        "android.permission.PROCESS_OUTGOING_CALLS",
        "android.permission.READ_PHONE_STATE",
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
            "Manifest permissions must match the muse launch allow-list",
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
            "Application must use @string/app_name (muse is set in strings.xml)",
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
