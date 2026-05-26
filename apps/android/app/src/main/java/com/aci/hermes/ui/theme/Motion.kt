package com.aci.hermes.ui.theme

import android.content.Context
import android.provider.Settings
import androidx.compose.runtime.Composable
import androidx.compose.runtime.ReadOnlyComposable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.platform.LocalContext

/**
 * Snapshot of the user's reduce-motion preference. We honor the
 * device-level animator-duration-scale because Android does not expose
 * a single "reduce motion" toggle below API 33 — when the user has
 * turned animations off in Developer Options or the accessibility
 * shortcut, [reduced] is true and decorative animations should fall
 * back to a non-animated state.
 */
data class MotionPreferences(val reduced: Boolean = false)

val LocalMotion = staticCompositionLocalOf { MotionPreferences() }

@Composable
@ReadOnlyComposable
fun rememberMotionPreferences(): MotionPreferences {
    val context = LocalContext.current
    return MotionPreferences(reduced = isMotionReduced(context))
}

private fun isMotionReduced(context: Context): Boolean {
    return try {
        val scale = Settings.Global.getFloat(
            context.contentResolver,
            Settings.Global.ANIMATOR_DURATION_SCALE,
            1f,
        )
        scale == 0f
    } catch (_: Settings.SettingNotFoundException) {
        false
    }
}
