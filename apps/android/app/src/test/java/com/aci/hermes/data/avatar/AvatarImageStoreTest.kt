package com.aci.hermes.data.avatar

import android.graphics.Bitmap
import androidx.test.core.app.ApplicationProvider
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.io.File

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [33])
class AvatarImageStoreTest {

    private lateinit var store: AvatarImageStore

    @Before
    fun setUp() {
        val ctx = ApplicationProvider.getApplicationContext<android.content.Context>()
        store = AvatarImageStore(ctx)
        store.deleteAll()
    }

    @Test
    fun savedFileLivesUnderAppPrivateDir() {
        val bmp = Bitmap.createBitmap(8, 8, Bitmap.Config.ARGB_8888)
        val out = store.saveBitmapAsPng(bmp, "avatar_test.png")
        assertTrue("expected ${out.absolutePath} to live under ${store.directory.absolutePath}", store.pathInAppPrivate(out))
        assertTrue(out.exists())
    }

    @Test
    fun externalPathsAreRejected() {
        val external = File("/sdcard/Pictures/avatar.png")
        assertFalse(store.pathInAppPrivate(external))
        val tmp = File("/tmp/avatar.png")
        assertFalse(store.pathInAppPrivate(tmp))
    }

    @Test
    fun deleteAllClearsTheDirectory() {
        val bmp = Bitmap.createBitmap(8, 8, Bitmap.Config.ARGB_8888)
        store.saveBitmapAsPng(bmp, "a.png")
        store.saveBitmapAsPng(bmp, "b.png")
        store.deleteAll()
        assertEquals(0, store.directory.listFiles()?.size ?: 0)
    }

    @Test
    fun currentAvatarFileReturnsNewest() {
        val bmp = Bitmap.createBitmap(8, 8, Bitmap.Config.ARGB_8888)
        val first = store.saveBitmapAsPng(bmp, "old.png")
        first.setLastModified(1_000L)
        val newest = store.saveBitmapAsPng(bmp, "new.png")
        newest.setLastModified(9_999L)
        val current = store.currentAvatarFile()
        assertNotNull(current)
        assertEquals("new.png", current!!.name)
    }
}
