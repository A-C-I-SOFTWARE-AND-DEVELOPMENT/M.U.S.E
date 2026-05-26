package com.aci.hermes.ui.jarvis

import android.provider.Settings
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.platform.LocalContext

/**
 * Reads the system "Remove animations" / animator-duration-scale
 * preference. Returns true when the user has asked for reduced
 * motion. The composable that owns the icon passes this flag to
 * [JarvisPrimeIcon] so the infinite pulse is suppressed.
 *
 * Implementation note: Android does not expose a dedicated
 * "reduce motion" toggle on every OEM. We treat both transition and
 * animator duration scale being zeroed as the user's intent.
 */
@Composable
fun rememberReducedMotion(): Boolean {
    val context = LocalContext.current
    return remember(context.contentResolver) {
        val animator = runCatching {
            Settings.Global.getFloat(
                context.contentResolver,
                Settings.Global.ANIMATOR_DURATION_SCALE,
                1f,
            )
        }.getOrDefault(1f)
        val transition = runCatching {
            Settings.Global.getFloat(
                context.contentResolver,
                Settings.Global.TRANSITION_ANIMATION_SCALE,
                1f,
            )
        }.getOrDefault(1f)
        animator == 0f && transition == 0f
    }
}
