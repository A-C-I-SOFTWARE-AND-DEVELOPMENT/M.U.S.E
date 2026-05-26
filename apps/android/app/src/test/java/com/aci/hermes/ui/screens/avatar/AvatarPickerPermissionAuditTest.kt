package com.aci.hermes.ui.screens.avatar

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * The avatar picker's contract is: **zero new manifest permissions.**
 *
 * The Android Photo Picker (`ActivityResultContracts.PickVisualMedia`)
 * does not require `READ_MEDIA_IMAGES`, `READ_EXTERNAL_STORAGE`, or
 * any other media permission. The URI it returns carries one-shot
 * read permission via a grant on the calling activity.
 *
 * This test parses `AndroidManifest.xml` and pins the
 * `<uses-permission>` set to the launch allowlist. Any drift —
 * a stray `READ_MEDIA_IMAGES`, a `CAMERA`, a `RECORD_AUDIO` — fails
 * the build before it ships.
 *
 * Mirrors the spirit of `ManifestPermissionsTest` (lane 3) and
 * `AndroidManifestPermissionsTest` (lane 8). Three independent
 * tests is by design — duplication is cheaper than a permission
 * leak.
 */
class AvatarPickerPermissionAuditTest {

    private val launchAllowlist: Set<String> = setOf(
        "android.permission.POST_NOTIFICATIONS",
        "android.permission.FOREGROUND_SERVICE",
        "android.permission.FOREGROUND_SERVICE_DATA_SYNC",
    )

    private val forbidden: Set<String> = setOf(
        "android.permission.READ_MEDIA_IMAGES",
        "android.permission.READ_MEDIA_VIDEO",
        "android.permission.READ_MEDIA_AUDIO",
        "android.permission.READ_MEDIA_VISUAL_USER_SELECTED",
        "android.permission.READ_EXTERNAL_STORAGE",
        "android.permission.WRITE_EXTERNAL_STORAGE",
        "android.permission.MANAGE_EXTERNAL_STORAGE",
        "android.permission.RECORD_AUDIO",
        "android.permission.SYSTEM_ALERT_WINDOW",
        "android.permission.CAMERA",
        "android.permission.ACCESS_FINE_LOCATION",
        "android.permission.ACCESS_COARSE_LOCATION",
    )

    @Test
    fun manifest_permission_set_matches_launch_allowlist_exactly() {
        val manifest = File("src/main/AndroidManifest.xml")
        assertTrue(
            "manifest must exist at ${manifest.absolutePath}",
            manifest.exists(),
        )
        val declared = parsePermissions(manifest.readText())
        assertEquals(
            "manifest permission set must match the launch allowlist exactly. " +
                "Declared: $declared, allowlist: $launchAllowlist",
            launchAllowlist,
            declared,
        )
    }

    @Test
    fun manifest_does_not_declare_any_forbidden_permission() {
        val manifest = File("src/main/AndroidManifest.xml").readText()
        val declared = parsePermissions(manifest)
        val violations = declared.intersect(forbidden)
        assertEquals(
            "manifest must not declare any forbidden permission. " +
                "Violations: $violations",
            emptySet<String>(),
            violations,
        )
    }

    private fun parsePermissions(manifest: String): Set<String> {
        val pattern = Regex("""<uses-permission\s+android:name="([^"]+)"""")
        return pattern.findAll(manifest).map { it.groupValues[1] }.toSet()
    }
}
