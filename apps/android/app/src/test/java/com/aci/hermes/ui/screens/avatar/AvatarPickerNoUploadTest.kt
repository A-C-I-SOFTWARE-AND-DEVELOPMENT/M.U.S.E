package com.aci.hermes.ui.screens.avatar

import org.junit.Assert.assertEquals
import org.junit.Test
import java.io.File

/**
 * AST-style guard: the avatar-picker surface must never import a
 * network type. Pixelation is local-only, storage is app-private,
 * and the photo URI is one-shot — nothing should leave the device.
 *
 * This scan checks the production sources under
 * `src/main/java/com/aci/hermes/ui/screens/avatar/` against a
 * deny-list of known network roots. A future refactor that quietly
 * adds `import okhttp3.*` to `AvatarPickerViewModel` would fail
 * this test before it ships.
 */
class AvatarPickerNoUploadTest {

    private val forbiddenImports = listOf(
        "okhttp3.",
        "okio.",
        "retrofit2.",
        "java.net.HttpURLConnection",
        "java.net.URLConnection",
        "java.net.URL",
        "java.net.Socket",
        "java.net.InetAddress",
        "android.net.http.",
        "androidx.work.WorkManager", // background uploads sneak in here
    )

    @Test
    fun avatar_picker_sources_import_zero_network_types() {
        val dir = File("src/main/java/com/aci/hermes/ui/screens/avatar")
        // The test runs from `apps/android/app/` — the working
        // directory `:app:testDebugUnitTest` runs from.
        assertEquals(
            "avatar picker source tree must exist at " + dir.absolutePath,
            true,
            dir.exists(),
        )

        val violations = mutableListOf<String>()
        dir.walkTopDown()
            .filter { it.isFile && it.extension == "kt" }
            .forEach { file ->
                file.readLines().forEachIndexed { index, line ->
                    val trimmed = line.trim()
                    if (!trimmed.startsWith("import ")) return@forEachIndexed
                    for (forbidden in forbiddenImports) {
                        if (forbidden in trimmed) {
                            violations += "${file.name}:${index + 1}  $trimmed"
                        }
                    }
                }
            }

        assertEquals(
            "avatar picker must not import any network type. Found:\n" +
                violations.joinToString("\n"),
            0,
            violations.size,
        )
    }
}
