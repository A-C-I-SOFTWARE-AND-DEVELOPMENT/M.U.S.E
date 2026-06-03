package com.aci.hermes.ui.screens.live

import androidx.compose.foundation.Canvas
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color

/**
 * A cozy pixel-art **bedroom** for the companion's Den — wall, window with a
 * night sky, a wooden floor, a desk/workspace, a bed mat the companion snoozes
 * on, and a plant. Drawn as crisp pixel blocks so it sits behind the
 * pixel-sprite avatar in the same aesthetic. Scales to any canvas size.
 *
 * Later this becomes editable (themes + AI-generated furniture); for now it's a
 * fixed, hand-built room.
 */
@Composable
fun PixelRoom(modifier: Modifier = Modifier) {
    Canvas(modifier = modifier) {
        val w = size.width
        val h = size.height
        // Pixel grid: draw on a virtual 32-wide grid so blocks read as pixels.
        val cols = 32
        val px = w / cols
        fun block(cx: Float, cy: Float, cw: Float, ch: Float, color: Color) {
            drawRect(color, Offset(cx * px, cy * px), Size(cw * px + 0.6f, ch * px + 0.6f))
        }
        val rows = h / px

        val wall = Color(0xFF2A2440)
        val wallLo = Color(0xFF221D36)
        val floor = Color(0xFF4A3A2A)
        val floorHi = Color(0xFF5A4632)
        val sky = Color(0xFF0E1330)
        val moon = Color(0xFFE7E0C8)
        val star = Color(0xFFBFD0FF)
        val wood = Color(0xFF6B4A2C)
        val woodHi = Color(0xFF855E38)
        val lamp = Color(0xFFE7B24A)
        val bed = Color(0xFF2E6E7E)
        val bedHi = Color(0xFF3C8A9C)
        val plant = Color(0xFF3E7D45)
        val pot = Color(0xFFB4632E)

        val floorTop = rows * 0.64f

        // Wall + floor
        block(0f, 0f, cols.toFloat(), floorTop, wall)
        block(0f, floorTop - 0.5f, cols.toFloat(), 0.5f, wallLo)
        block(0f, floorTop, cols.toFloat(), rows - floorTop, floor)
        // floor planks (a few highlight lines)
        var fy = floorTop + 1.5f
        while (fy < rows) {
            block(0f, fy, cols.toFloat(), 0.18f, floorHi)
            fy += 2.2f
        }

        // Window with night sky + moon + stars (upper-left)
        block(3f, 2f, 9f, 6f, sky)
        block(2.6f, 1.6f, 9.8f, 0.4f, wood)        // frame top
        block(2.6f, 8f, 9.8f, 0.4f, wood)          // frame bottom
        block(7.3f, 2f, 0.4f, 6f, wood)            // mullion
        block(9.5f, 3f, 1.4f, 1.4f, moon)          // moon
        block(4f, 3.2f, 0.4f, 0.4f, star)
        block(5.6f, 5.4f, 0.4f, 0.4f, star)
        block(6.6f, 3.6f, 0.3f, 0.3f, star)

        // Desk / workspace (right wall), with a lamp
        val deskY = floorTop - 3.2f
        block(20f, deskY, 9f, 0.7f, woodHi)        // desktop
        block(20.5f, deskY + 0.7f, 0.7f, 3f, wood) // leg
        block(27.5f, deskY + 0.7f, 0.7f, 3f, wood) // leg
        block(26.5f, deskY - 2.4f, 0.5f, 2.4f, wood) // lamp arm
        block(25.8f, deskY - 2.9f, 1.9f, 0.7f, lamp)  // lamp head
        block(21f, deskY - 1.2f, 2.6f, 1.2f, Color(0xFF3A3350)) // a screen/book

        // Bed mat (bottom-centre) — where the companion curls up to snooze.
        val matY = rows - 2.4f
        block(11f, matY, 10f, 1.9f, bed)
        block(11f, matY, 10f, 0.5f, bedHi)
        block(11f, matY, 3f, 1.9f, bedHi)          // pillow end

        // Plant (bottom-left corner)
        block(1.6f, rows - 3.4f, 2.4f, 2.0f, plant)
        block(2.1f, rows - 1.4f, 1.4f, 1.2f, pot)
    }
}
