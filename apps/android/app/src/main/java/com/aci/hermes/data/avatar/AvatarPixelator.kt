package com.aci.hermes.data.avatar

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Color
import android.net.Uri
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import java.io.IOException

class AvatarPixelator(
    private val context: Context,
    private val imageStore: AvatarImageStore = AvatarImageStore(context),
) {

    suspend fun pixelate(uri: Uri, pixelSize: PixelSize, style: AvatarStyle): File =
        withContext(Dispatchers.IO) {
            val decoded = decodeBoundedBitmap(uri)
                ?: throw IOException("Unable to decode image from Uri")
            val square = centerCropSquare(decoded)
            if (square !== decoded) decoded.recycle()

            val down = downscale(square, pixelSize.px)
            if (down !== square) square.recycle()

            val styled = applyStyle(down, style)
            if (styled !== down) down.recycle()

            val upscaled = upscaleNearest(styled, OUTPUT_SIZE_PX)
            if (upscaled !== styled) styled.recycle()

            val fileName = "avatar_${System.currentTimeMillis()}.png"
            val file = imageStore.saveBitmapAsPng(upscaled, fileName)
            upscaled.recycle()
            file
        }

    internal fun decodeBoundedBitmap(uri: Uri): Bitmap? {
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        context.contentResolver.openInputStream(uri).use { input ->
            if (input == null) return null
            BitmapFactory.decodeStream(input, null, bounds)
        }
        if (bounds.outWidth <= 0 || bounds.outHeight <= 0) return null

        var sample = 1
        val maxDim = maxOf(bounds.outWidth, bounds.outHeight)
        while (maxDim / sample > DECODE_MAX_DIM) sample *= 2

        val opts = BitmapFactory.Options().apply {
            inSampleSize = sample
            inPreferredConfig = Bitmap.Config.ARGB_8888
        }
        return context.contentResolver.openInputStream(uri).use { input ->
            if (input == null) null else BitmapFactory.decodeStream(input, null, opts)
        }
    }

    internal fun centerCropSquare(src: Bitmap): Bitmap {
        if (src.width == src.height) return src
        val side = minOf(src.width, src.height)
        val x = (src.width - side) / 2
        val y = (src.height - side) / 2
        return Bitmap.createBitmap(src, x, y, side, side)
    }

    internal fun downscale(src: Bitmap, sizePx: Int): Bitmap {
        if (src.width == sizePx && src.height == sizePx) return src
        // filter=true smooths the source before pixelation; the next step
        // (upscale with filter=false) preserves the chunky-pixel look.
        return Bitmap.createScaledBitmap(src, sizePx, sizePx, true)
    }

    internal fun upscaleNearest(src: Bitmap, sizePx: Int): Bitmap {
        if (src.width == sizePx && src.height == sizePx) return src
        return Bitmap.createScaledBitmap(src, sizePx, sizePx, false)
    }

    internal fun applyStyle(src: Bitmap, style: AvatarStyle): Bitmap {
        if (style == AvatarStyle.NONE) return src
        val w = src.width
        val h = src.height
        val pixels = IntArray(w * h)
        src.getPixels(pixels, 0, w, 0, 0, w, h)
        for (i in pixels.indices) {
            pixels[i] = transformPixel(pixels[i], style)
        }
        val out = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888)
        out.setPixels(pixels, 0, w, 0, 0, w, h)
        return out
    }

    private fun transformPixel(argb: Int, style: AvatarStyle): Int {
        val a = Color.alpha(argb)
        val r = Color.red(argb)
        val g = Color.green(argb)
        val b = Color.blue(argb)
        val lum = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0
        return when (style) {
            AvatarStyle.NONE -> argb
            AvatarStyle.NAVY_GOLD -> duotone(a, lum, NAVY, GOLD)
            AvatarStyle.CYAN_GLOW -> duotone(a, lum, CYAN_DARK, CYAN_BRIGHT)
            AvatarStyle.MONOCHROME_TERMINAL -> {
                val v = (lum * 255).toInt().coerceIn(0, 255)
                Color.argb(a, v, v, v)
            }
        }
    }

    private fun duotone(alpha: Int, lum: Double, dark: Int, light: Int): Int {
        val r = mix(Color.red(dark), Color.red(light), lum)
        val g = mix(Color.green(dark), Color.green(light), lum)
        val b = mix(Color.blue(dark), Color.blue(light), lum)
        return Color.argb(alpha, r, g, b)
    }

    private fun mix(low: Int, high: Int, t: Double): Int =
        (low + (high - low) * t).toInt().coerceIn(0, 255)

    companion object {
        const val OUTPUT_SIZE_PX = 256
        private const val DECODE_MAX_DIM = 1024

        private val NAVY = Color.rgb(0x0a, 0x1f, 0x44)
        private val GOLD = Color.rgb(0xd4, 0xaf, 0x37)
        private val CYAN_DARK = Color.rgb(0x00, 0x1a, 0x33)
        private val CYAN_BRIGHT = Color.rgb(0x66, 0xff, 0xff)
    }
}
