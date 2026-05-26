package com.aci.hermes.manifest

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import java.io.File

/**
 * Guards against accidentally introducing a second Android app package
 * (e.g. `com.jeremiahecherd.jarvisprime`, `com.example.jarvis`, …)
 * inside the apps/android/app module. Every Kotlin / Java source file
 * under the main + test source sets must declare a package that begins
 * with `com.aci.hermes`.
 */
class PackageUniquenessTest {

    private val expectedRoot = "com.aci.hermes"

    @Test
    fun `every kotlin source file declares a com_aci_hermes package`() {
        val violations = collectPackages(setOf("src/main/java", "src/test/java"))
            .filterNot { (_, pkg) -> pkg == expectedRoot || pkg.startsWith("$expectedRoot.") }
        assertTrue(
            "All sources must live under $expectedRoot. Offenders:\n" +
                violations.joinToString("\n") { (path, pkg) -> "  $path → $pkg" },
            violations.isEmpty(),
        )
    }

    @Test
    fun `at least one main source file is under com_aci_hermes`() {
        // Sanity floor: the resolution helpers must find something.
        // If this fails, the helpers are looking in the wrong place.
        val mainPackages = collectPackages(setOf("src/main/java"))
        assertTrue("Expected to find at least one main source file", mainPackages.isNotEmpty())
        val rooted = mainPackages.count { (_, pkg) ->
            pkg == expectedRoot || pkg.startsWith("$expectedRoot.")
        }
        assertEquals(
            "Every main source file must live under $expectedRoot",
            mainPackages.size,
            rooted,
        )
    }

    private fun collectPackages(sourceSetRelatives: Set<String>): List<Pair<String, String>> {
        val moduleRoot = resolveModuleRoot()
        val results = mutableListOf<Pair<String, String>>()
        for (rel in sourceSetRelatives) {
            val root = File(moduleRoot, rel)
            if (!root.isDirectory) continue
            root.walkTopDown()
                .filter { it.isFile && (it.extension == "kt" || it.extension == "java") }
                .forEach { file ->
                    val pkg = readPackage(file)
                    if (pkg != null) {
                        val display = file.relativeTo(moduleRoot).path
                        results += display to pkg
                    }
                }
        }
        return results
    }

    private fun readPackage(file: File): String? {
        val pkgRegex = Regex("""^\s*package\s+([\w.]+)""", RegexOption.MULTILINE)
        val text = file.readText()
        return pkgRegex.find(text)?.groupValues?.get(1)
    }

    private fun resolveModuleRoot(): File {
        val candidates = mutableListOf<File>()
        val startCwd: String = System.getProperty("user.dir") ?: "."
        var here: File? = File(startCwd)
        while (here != null) {
            candidates += File(here, "apps/android/app")
            candidates += here
            here = here.parentFile
        }
        for (c in candidates) {
            if (File(c, "src/main/java").isDirectory) return c
        }
        fail("Could not locate apps/android/app module root from cwd $startCwd")
        return File(startCwd)
    }
}
