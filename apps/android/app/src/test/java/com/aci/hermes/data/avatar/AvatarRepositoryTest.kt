package com.aci.hermes.data.avatar

import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import androidx.test.core.app.ApplicationProvider
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.io.File

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [33])
class AvatarRepositoryTest {

    @get:Rule
    val tmp = TemporaryFolder()

    private lateinit var dataStore: DataStore<Preferences>
    private lateinit var imageStore: AvatarImageStore
    private lateinit var repo: AvatarRepository

    @Before
    fun setUp() {
        val ctx = ApplicationProvider.getApplicationContext<android.content.Context>()
        val prefsFile = File(tmp.newFolder(), "avatar_prefs_test.preferences_pb")
        dataStore = PreferenceDataStoreFactory.create { prefsFile }
        imageStore = AvatarImageStore(ctx)
        imageStore.deleteAll()
        repo = AvatarRepository(ctx, imageStore, dataStore)
    }

    @After
    fun tearDown() {
        imageStore.deleteAll()
    }

    @Test
    fun saveAndLoadBuiltinProfileRoundTrips() = runBlocking {
        val profile = AvatarProfile(
            source = AvatarSource.BUILTIN,
            builtin = JarvisBuiltin.GUARDIAN_SHIELD,
            generatedPath = null,
            pixelSize = PixelSize.DETAILED_48,
            style = AvatarStyle.CYAN_GLOW,
        )
        repo.save(profile)
        val loaded = repo.profileFlow.first()
        assertEquals(profile, loaded)
    }

    @Test
    fun saveAndLoadGeneratedProfileRoundTrips() = runBlocking {
        val generated = File(imageStore.directory, "rt_${System.nanoTime()}.png").apply {
            writeBytes(byteArrayOf(0x89.toByte(), 0x50, 0x4E, 0x47))
        }
        val profile = AvatarProfile(
            source = AvatarSource.GENERATED,
            builtin = null,
            generatedPath = generated.absolutePath,
            pixelSize = PixelSize.CHUNKY_16,
            style = AvatarStyle.MONOCHROME_TERMINAL,
        )
        repo.save(profile)
        val loaded = repo.profileFlow.first()
        assertEquals(profile, loaded)
    }

    @Test
    fun savedJsonDoesNotContainPickerSourceUri() = runBlocking {
        // Simulate the picker URI that is held only in memory and must
        // NEVER appear in persisted bytes.
        val pickerUri = "content://media/external/images/media/12345"
        val generated = File(imageStore.directory, "g_${System.nanoTime()}.png").apply {
            writeBytes(byteArrayOf(0))
        }
        val profile = AvatarProfile(
            source = AvatarSource.GENERATED,
            builtin = null,
            generatedPath = generated.absolutePath,
            pixelSize = PixelSize.BALANCED_32,
            style = AvatarStyle.NAVY_GOLD,
        )
        repo.save(profile)
        // Read the underlying preferences value directly to inspect it.
        val raw = dataStore.data.first().asMap().entries
            .single { it.key.name == "profile_json" }
            .value as String
        assertFalse("persisted JSON must not contain the picker URI", raw.contains(pickerUri))
        assertFalse("persisted JSON must not contain content:// scheme", raw.contains("content://"))
    }

    @Test
    fun clearEmptiesFlowAndImageStore() = runBlocking {
        val generated = File(imageStore.directory, "c_${System.nanoTime()}.png").apply {
            writeBytes(byteArrayOf(0))
        }
        repo.save(
            AvatarProfile(
                source = AvatarSource.GENERATED,
                builtin = null,
                generatedPath = generated.absolutePath,
                pixelSize = PixelSize.BALANCED_32,
                style = AvatarStyle.NAVY_GOLD,
            ),
        )
        assertNotNull(repo.profileFlow.first())
        repo.clear()
        assertNull(repo.profileFlow.first())
        assertEquals(0, imageStore.directory.listFiles()?.size ?: 0)
    }
}
