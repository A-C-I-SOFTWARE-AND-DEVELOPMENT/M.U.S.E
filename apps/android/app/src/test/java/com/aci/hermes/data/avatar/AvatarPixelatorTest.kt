package com.aci.hermes.data.avatar

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Color
import android.net.Uri
import androidx.test.core.app.ApplicationProvider
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import java.io.File
import java.io.FileOutputStream

@RunWith(RobolectricTestRunner::class)
class AvatarPixelatorTest {

    private lateinit var context: Context
    private lateinit var imageStore: AvatarImageStore
    private lateinit var pixelator: AvatarPixelator

    @Before
    fun setUp() {
        context = ApplicationProvider.getApplicationContext()
        imageStore = AvatarImageStore(context)
        imageStore.deleteAll()
        pixelator = AvatarPixelator(context, imageStore)
    }

    @Test
    fun outputIsSquareAt256x256() = runBlocking {
        val uri = writeSolidBitmap(64, 64, Color.RED)
        val out = pixelator.pixelate(uri, PixelSize.BALANCED_32, AvatarStyle.NONE)
        val decoded = android.graphics.BitmapFactory.decodeFile(out.absolutePath)
        assertEquals(256, decoded.width)
        assertEquals(256, decoded.height)
        assertEquals(decoded.width, decoded.height)
    }

    @Test
    fun outputFileIsInAppPrivateStorage() = runBlocking {
        val uri = writeSolidBitmap(64, 64, Color.BLUE)
        val out = pixelator.pixelate(uri, PixelSize.CHUNKY_16, AvatarStyle.NONE)
        assertTrue(
            "expected output ${out.absolutePath} under ${imageStore.directory.absolutePath}",
            imageStore.pathInAppPrivate(out),
        )
    }

    @Test
    fun nearestNeighborPreservesSolidColorWithStyleNone() = runBlocking {
        val uri = writeSolidBitmap(64, 64, Color.rgb(0x33, 0x66, 0x99))
        val out = pixelator.pixelate(uri, PixelSize.BALANCED_32, AvatarStyle.NONE)
        val decoded = android.graphics.BitmapFactory.decodeFile(out.absolutePath)
        val center = decoded.getPixel(decoded.width / 2, decoded.height / 2)
        // Allow a tiny tolerance: solid fill survives nearest-neighbor exactly,
        // but the intermediate filtered downscale on JVM is permitted small drift.
        assertEquals(Color.alpha(Color.rgb(0x33, 0x66, 0x99)), Color.alpha(center))
        assertTrue(Math.abs(Color.red(center) - 0x33) <= 4)
        assertTrue(Math.abs(Color.green(center) - 0x66) <= 4)
        assertTrue(Math.abs(Color.blue(center) - 0x99) <= 4)
    }

    @Test
    fun pickedUriPathIsNotPersisted() = runBlocking {
        val uri = writeSolidBitmap(64, 64, Color.GREEN)
        val out = pixelator.pixelate(uri, PixelSize.BALANCED_32, AvatarStyle.NAVY_GOLD)
        // The output filename must NOT contain the source uri path.
        assertTrue(out.name.startsWith("avatar_"))
        assertTrue(out.name.endsWith(".png"))
        assertEquals(false, out.absolutePath.contains(uri.path ?: "##"))
    }

    private fun writeSolidBitmap(w: Int, h: Int, color: Int): Uri {
        val bmp = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888)
        val pixels = IntArray(w * h) { color }
        bmp.setPixels(pixels, 0, w, 0, 0, w, h)
        val dir = File(context.cacheDir, "test-sources").apply { mkdirs() }
        val file = File(dir, "src_${System.nanoTime()}.png")
        FileOutputStream(file).use { bmp.compress(Bitmap.CompressFormat.PNG, 100, it) }
        return Uri.fromFile(file)
    }
}
