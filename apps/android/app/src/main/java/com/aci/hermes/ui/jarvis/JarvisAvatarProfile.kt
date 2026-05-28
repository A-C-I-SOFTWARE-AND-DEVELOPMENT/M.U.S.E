package com.aci.hermes.ui.jarvis

/**
 * Currently-selected avatar identity. The avatar is purely cosmetic
 * — the safety contract (emergency stop, approvals, owner gates) is
 * driven by [IconState] and the runtime, not by which face is shown.
 *
 * Two sources are supported:
 *  - [Source.BuiltIn]      — one of the bundled defaults (drawable resource id).
 *  - [Source.UserGenerated]— a user-picked image pixelated on-device
 *                            and stored under `context.filesDir/avatars/`.
 *                            The image is never uploaded.
 *
 * `selectedAt` is wall-clock millis at last selection; useful for
 * audit + tie-breaking when multiple profiles exist.
 */
data class JarvisAvatarProfile(
    val name: String,
    val source: Source,
    val selectedAt: Long,
) {
    sealed interface Source {
        data class BuiltIn(val drawableResId: Int) : Source
        data class UserGenerated(val filePath: String) : Source
    }

    companion object {
        /**
         * The default profile shipped on a fresh install. Resolved to
         * a real drawable resource id at construction time by
         * `DefaultAvatars` (see the avatar-picker branch).
         */
        const val DEFAULT_NAME: String = "Jarvis"
    }
}
