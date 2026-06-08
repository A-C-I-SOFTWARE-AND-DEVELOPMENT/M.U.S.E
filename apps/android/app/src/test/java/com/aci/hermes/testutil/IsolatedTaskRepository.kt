package com.aci.hermes.testutil

import android.content.Context
import com.aci.hermes.data.orchestrator.HermesTaskRepository
import java.nio.file.Files

/**
 * A [HermesTaskRepository] backed by a fresh, isolated directory under the JVM
 * temp dir instead of `context.filesDir`.
 *
 * `HermesTaskRepository` reads its backing JSON file on `Dispatchers.IO` from
 * `init { scope.launch { loadFromDisk() } }`. Under Robolectric a sandbox's
 * `filesDir` is recycled at test boundaries; a load still draining IO when that
 * happens reads a since-deleted file and surfaces a TOCTOU
 * `FileNotFoundException`. This mirrors the failure (and the fix) documented on
 * [isolatedSettings]: pointing the store at the JVM temp dir
 * (`java.io.tmpdir`), which outlives every Robolectric sandbox, keeps the file
 * present for both the test's own reads and any lagging actor.
 * `Files.createTempDirectory` also gives per-call uniqueness so concurrent test
 * classes never share a backing file.
 */
fun isolatedTaskRepository(context: Context): HermesTaskRepository {
    val dir = Files.createTempDirectory("hermes-tasks-test").toFile()
    dir.deleteOnExit()
    return HermesTaskRepository(context, baseDir = dir)
}
