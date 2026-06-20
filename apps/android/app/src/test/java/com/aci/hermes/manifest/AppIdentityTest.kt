package com.aci.hermes.manifest

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import java.io.File

/**
 * Pins the muse user-facing identity and the technical
 * package identifier.
 *
 *   * User-facing name (everywhere a label is rendered): "muse"
 *   * Technical package / applicationId / namespace: com.aci.hermes
 *
 * These two NEVER move during a launch-stabilization PR.
 */
class AppIdentityTest {

    @Test
    fun `app_name in strings_xml is exactly muse`() {
        val strings = readXml("src/main/res/values/strings.xml")
        val match = Regex("""<string\s+name="app_name"\s*>([^<]+)</string>""")
            .find(strings)
        assertTrue(
            "strings.xml must declare a single <string name=\"app_name\">",
            match != null,
        )
        assertEquals(
            "User-facing app name must be 'muse'",
            "muse",
            match!!.groupValues[1],
        )
    }

    @Test
    fun `application id is com_aci_hermes and appears exactly once`() {
        val gradle = readModuleText("build.gradle.kts")
        val applicationIdRegex = Regex("""applicationId\s*=\s*"([^"]+)"""")
        val matches = applicationIdRegex.findAll(gradle).toList()
        assertEquals(
            "Exactly one applicationId line must exist in app/build.gradle.kts",
            1,
            matches.size,
        )
        assertEquals("com.aci.hermes", matches[0].groupValues[1])
    }

    @Test
    fun `namespace is com_aci_hermes`() {
        val gradle = readModuleText("build.gradle.kts")
        val namespaceRegex = Regex("""namespace\s*=\s*"([^"]+)"""")
        val match = namespaceRegex.find(gradle)
        assertTrue("build.gradle.kts must declare a namespace", match != null)
        assertEquals("com.aci.hermes", match!!.groupValues[1])
    }

    private fun readXml(relativePath: String): String = readModuleText(relativePath)

    private fun readModuleText(relativePath: String): String {
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
