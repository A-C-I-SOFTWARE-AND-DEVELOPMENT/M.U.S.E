package com.jeremiahecherd.jarvisprime.permissions

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.content.ContextCompat

/**
 * Tiny, side-effect-free helpers around the runtime permissions
 * Jarvis Prime touches. Nothing here actually shows a system prompt;
 * the prompt is launched from a Compose
 * `rememberLauncherForActivityResult` only after the user taps an
 * explicit opt-in inside an education card.
 */
object PermissionHelpers {

    /** Android 13 (API 33) introduced the runtime POST_NOTIFICATIONS prompt. */
    fun notificationRuntimePromptRequired(): Boolean =
        Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU

    fun hasNotificationPermission(context: Context): Boolean {
        if (!notificationRuntimePromptRequired()) return true
        return ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.POST_NOTIFICATIONS,
        ) == PackageManager.PERMISSION_GRANTED
    }

    fun hasMicrophonePermission(context: Context): Boolean =
        ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.RECORD_AUDIO,
        ) == PackageManager.PERMISSION_GRANTED
}
