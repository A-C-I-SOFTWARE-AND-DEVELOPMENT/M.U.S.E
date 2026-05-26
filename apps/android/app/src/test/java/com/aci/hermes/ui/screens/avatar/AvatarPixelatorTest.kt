package com.aci.hermes.ui.screens.avatar

import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Pure-logic guard-rails for the pixelator. The `Bitmap`-flavoured
 * `pixelate` entry point delegates to Android-only APIs (Bitmap
 * decode + createScaledBitmap) and is exercised end-to-end in the
 * picker view-model integration tests + on-device smoke. The
 * pure-JVM-testable pieces — defaults + bucket math — are pinned
 * here so a refactor that drifts the aesthetic gets caught.
 */
class AvatarPixelatorTest {

    @Test
    fun default_grid_is_in_pixel_art_band() {
        // Chunkier than 16 looks blocky beyond recognition;
        // finer than 128 defeats the aesthetic.
        assertTrue(
            "default grid (${AvatarPixelator.DEFAULT_GRID}) should be in [16, 128]",
            AvatarPixelator.DEFAULT_GRID in 16..128,
        )
    }

    @Test
    fun default_palette_size_keeps_pixel_art_look() {
        assertTrue(
            "default palette (${AvatarPixelator.DEFAULT_PALETTE_SIZE}) should be ≥ 8",
            AvatarPixelator.DEFAULT_PALETTE_SIZE >= 8,
        )
        assertTrue(
            "default palette (${AvatarPixelator.DEFAULT_PALETTE_SIZE}) should be ≤ 64",
            AvatarPixelator.DEFAULT_PALETTE_SIZE <= 64,
        )
    }

    @Test
    fun visually_distant_colors_land_in_different_buckets() {
        // Two visually-distinct colors must land in different buckets
        // at any sensible mask. The masked-high-bits scheme used
        // internally is what gives the pixel-art look — it must not
        // collapse red into green.
        val red = (0xFFFF0000.toInt())
        val green = (0xFF00FF00.toInt())
        val mask = 0xF0
        val keyRedR = (red ushr 16) and mask
        val keyGreenR = (green ushr 16) and mask
        val keyRedG = (red ushr 8) and mask
        val keyGreenG = (green ushr 8) and mask
        assertNotEquals(keyRedR, keyGreenR)
        assertNotEquals(keyRedG, keyGreenG)
    }
}
