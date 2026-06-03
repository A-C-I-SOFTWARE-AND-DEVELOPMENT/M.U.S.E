package com.aci.hermes.testutil

import android.content.Context
import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import com.aci.hermes.data.preferences.SettingsRepository
import java.io.File

/**
 * A [SettingsRepository] backed by a fresh, isolated DataStore file.
 *
 * The production repository uses a process-wide `preferencesDataStore`
 * singleton, which under Robolectric is shared across every test class in the
 * JVM — it leaks state between cases and can go stale once a prior class has
 * initialised it. Injecting a per-call store (the same seam AvatarRepository
 * already exposes) makes every settings-backed ViewModel test hermetic and
 * deterministic.
 */
fun isolatedSettings(context: Context): SettingsRepository {
    val dir = File(context.cacheDir, "settings-test-${System.nanoTime()}")
    dir.mkdirs()
    val store = PreferenceDataStoreFactory.create { File(dir, "settings.preferences_pb") }
    return SettingsRepository(context, store)
}
