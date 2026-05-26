package com.aci.hermes.ui.screens.avatar

import android.graphics.Bitmap

/**
 * Pure pixel-art transform. Two-pass:
 *  1. Downsample with `filter = false` to a small grid
 *     (default 64×64) so each source-region collapses into one
 *     hard-edged sample.
 *  2. Upscale back to the display size, again with `filter = false`,
 *     so the resulting image has crisp blocky edges instead of
 *     interpolated mush.
 *
 * Optionally quantizes the color palette to a small fixed count
 * (default 16) via the cheap "average-of-bucket" path — no ML, no
 * network, all work on the calling thread. The caller is expected to
 * dispatch to `Dispatchers.Default` or similar.
 *
 * The pixelator does not touch the filesystem — pure `Bitmap` → `Bitmap`.
 */
object AvatarPixelator {

    /** Default downsample grid. Lower = chunkier; higher = subtler. */
    const val DEFAULT_GRID: Int = 64

    /** Default quantized palette size. 16 keeps the pixel-art aesthetic. */
    const val DEFAULT_PALETTE_SIZE: Int = 16

    /**
     * Pixelate [source]. Returns a new bitmap; does not recycle [source].
     *
     * @param source the input image (e.g. from the Photo Picker).
     * @param outputSize side length of the returned bitmap (square).
     *                   The cockpit avatar slot is 192 dp; passing 192
     *                   pixels at hdpi → 288 dp visual; the screen
     *                   scales as needed.
     * @param grid the downsample grid side; smaller = chunkier.
     * @param paletteSize number of colors to quantize to. Pass 0 to
     *                    skip quantization.
     */
    fun pixelate(
        source: Bitmap,
        outputSize: Int = 384,
        grid: Int = DEFAULT_GRID,
        paletteSize: Int = DEFAULT_PALETTE_SIZE,
    ): Bitmap {
        require(outputSize > 0) { "outputSize must be positive" }
        require(grid in 1..outputSize) { "grid must be 1..outputSize" }
        require(paletteSize >= 0) { "paletteSize must be non-negative" }

        val downsampled = Bitmap.createScaledBitmap(source, grid, grid, false)
        val quantized = if (paletteSize == 0) downsampled else quantize(downsampled, paletteSize)
        val upscaled = Bitmap.createScaledBitmap(quantized, outputSize, outputSize, false)
        if (quantized !== downsampled) quantized.recycle()
        downsampled.recycle()
        return upscaled
    }

    /**
     * Color-bucket quantization. For each pixel, the high bits of each
     * channel pick a bucket; the bucket's average color replaces the
     * pixel. With `levels = 16` this yields a 16-color (well: up to
     * 16-color) palette of the dominant tones in the image.
     */
    internal fun quantize(source: Bitmap, levels: Int): Bitmap {
        if (levels <= 1) return source.copy(source.config ?: Bitmap.Config.ARGB_8888, true)
        val w = source.width
        val h = source.height
        val pixels = IntArray(w * h)
        source.getPixels(pixels, 0, w, 0, 0, w, h)
        val bits = bitsForLevels(levels)
        val mask = ((0xFF shr (8 - bits)) shl (8 - bits)) and 0xFF
        // Build the bucket → average map.
        val bucketSum = HashMap<Int, IntArray>()
        for (px in pixels) {
            val key = bucketKey(px, mask)
            val acc = bucketSum.getOrPut(key) { IntArray(5) }
            acc[0] += (px ushr 24) and 0xFF
            acc[1] += (px ushr 16) and 0xFF
            acc[2] += (px ushr 8) and 0xFF
            acc[3] += px and 0xFF
            acc[4] += 1
        }
        val palette = HashMap<Int, Int>(bucketSum.size)
        for ((key, acc) in bucketSum) {
            val n = acc[4]
            val a = acc[0] / n
            val r = acc[1] / n
            val g = acc[2] / n
            val b = acc[3] / n
            palette[key] = (a shl 24) or (r shl 16) or (g shl 8) or b
        }
        val out = IntArray(pixels.size)
        for (i in pixels.indices) {
            val key = bucketKey(pixels[i], mask)
            out[i] = palette[key] ?: pixels[i]
        }
        val result = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888)
        result.setPixels(out, 0, w, 0, 0, w, h)
        return result
    }

    private fun bucketKey(argb: Int, mask: Int): Int {
        val a = ((argb ushr 24) and 0xFF) and mask
        val r = ((argb ushr 16) and 0xFF) and mask
        val g = ((argb ushr 8) and 0xFF) and mask
        val b = (argb and 0xFF) and mask
        return (a shl 24) or (r shl 16) or (g shl 8) or b
    }

    /** ceil(log2(levels)), clipped to [1, 8]. */
    private fun bitsForLevels(levels: Int): Int {
        var n = 0
        var v = levels - 1
        while (v > 0) { n++; v = v ushr 1 }
        return n.coerceIn(1, 8)
    }
}
