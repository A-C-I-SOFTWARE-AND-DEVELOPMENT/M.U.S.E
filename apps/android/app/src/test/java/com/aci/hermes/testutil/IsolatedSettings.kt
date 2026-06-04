package com.aci.hermes.testutil

import android.content.Context
import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import com.aci.hermes.data.preferences.SettingsRepository
import java.io.File
import java.nio.file.Files

/**
 * A [SettingsRepository] backed by a fresh, isolated DataStore file.
 *
 * The production repository uses a process-wide `preferencesDataStore`
 * singleton, which under Robolectric is shared across every test class in the
 * JVM — it leaks state between cases and can go stale once a prior class has
 * initialised it. Injecting a per-call store (the same seam AvatarRepository
 * already exposes) makes every settings-backed ViewModel test hermetic and
 * deterministic.
 *
 * The backing file lives under the JVM temp dir (`java.io.tmpdir`), **not**
 * `context.cacheDir`. Robolectric recycles a sandbox's cache directory at test
 * boundaries; a DataStore actor still draining IO on `Dispatchers.IO` when that
 * happens reads a since-deleted file and surfaces a TOCTOU
 * `FileNotFoundException` (DataStore only swallows the missing-file case when
 * `file.exists()` is false, so a concurrent delete between the existence check
 * and the open rethrows). A JVM-stable temp dir outlives every Robolectric
 * sandbox, so the file is always present for both the test's own reads and any
 * lagging actor. `Files.createTempDirectory` also gives the per-call uniqueness
 * DataStore requires (one active instance per file).
 */
fun isolatedSettings(context: Context): SettingsRepository {
    val dir = Files.createTempDirectory("hermes-settings-test").toFile()
    dir.deleteOnExit()
    val store = PreferenceDataStoreFactory.create { File(dir, "settings.preferences_pb") }
    return SettingsRepository(context, store)
}
