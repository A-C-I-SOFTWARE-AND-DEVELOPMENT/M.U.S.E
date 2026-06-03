package com.aci.hermes.ui.screens.live

import android.graphics.Bitmap
import androidx.annotation.StringRes
import com.aci.hermes.R
import com.aci.hermes.data.life.AvatarBehavior

/**
 * Discrete states the Jarvis presence surface can occupy. Ordered by
 * priority — higher ordinal wins when multiple flags are set on the
 * raw [JarvisLiveUiState].
 */
enum class JarvisLiveState {
    Idle,
    Listening,
    Thinking,
    Working,
    Speaking,
    ApprovalNeeded,
    Blocked,
    EmergencyStop,
}

/**
 * The raw, multi-dimensional state held by [JarvisLiveViewModel].
 * It carries every flag the user-supplied agent runtime might raise at
 * once; the projector resolves it to a single [JarvisLiveState] for
 * display.
 */
data class JarvisLiveUiState(
    val listening: Boolean = false,
    val thinking: Boolean = false,
    val working: Boolean = false,
    val speaking: Boolean = false,
    val approvalNeeded: Boolean = false,
    val blocked: Boolean = false,
    val emergencyStop: Boolean = false,
    val voiceLine: String = "",
    val reducedMotion: Boolean = false,
    val command: String = "",
    val voiceAvailable: Boolean = false,
    // Default to the living humanoid body (breathes + moves); DeviceCapability
    // collapses it to the calm Orb under reduced motion / low-end devices.
    val avatarKind: AvatarKind = AvatarKind.Character3D,
    // Ambient life when idle — idle → wander → sleep, driven by BehaviorScheduler.
    val avatarBehavior: AvatarBehavior = AvatarBehavior.IDLE,
    // The user's saved photo avatar (when the picker produced a GENERATED one),
    // rendered as a living, breathing face. Null → use the procedural body.
    val avatarPhoto: Bitmap? = null,
)

/**
 * How the living avatar is rendered. [Orb] is the original abstract
 * renderer (also the reduced-motion / low-end fallback). [Pixel] /
 * [Photo] are the still pixel-art picker outputs. The three additive
 * kinds below are the "truly alive" character renderers:
 *  - [AnimatedPixel] — sprite-sheet character (run/push/sleep frames)
 *  - [Rive] — vector state-machine character (the default "alive" body)
 *  - [Character3D] — Filament-rendered glTF character (high-end devices)
 */
enum class AvatarKind { Orb, Pixel, Photo, AnimatedPixel, Rive, Character3D }

/**
 * The display-ready projection consumed by [JarvisLiveScreen]. All
 * user-visible text is returned as [StringRes] ids so this object can
 * be produced and unit-tested without an Android Context.
 */
data class JarvisLiveProjection(
    val state: JarvisLiveState,
    @StringRes val pillText: Int,
    @StringRes val voiceLineFallback: Int,
    @StringRes val contentDescription: Int,
    val motionEnabled: Boolean,
    val particlesEnabled: Boolean,
    val showApprovalCta: Boolean,
    val showFixCta: Boolean,
    val showEmergencyReleaseCta: Boolean,
) {
    val isEmergency: Boolean get() = state == JarvisLiveState.EmergencyStop
}

/** Default voice line resource keyed by projected state. */
@StringRes
fun defaultVoiceLineFor(state: JarvisLiveState): Int = when (state) {
    JarvisLiveState.Idle -> R.string.jarvis_voice_idle
    JarvisLiveState.Listening -> R.string.jarvis_voice_listening
    JarvisLiveState.Thinking -> R.string.jarvis_voice_thinking
    JarvisLiveState.Working -> R.string.jarvis_voice_working
    JarvisLiveState.Speaking -> R.string.jarvis_voice_speaking
    JarvisLiveState.ApprovalNeeded -> R.string.jarvis_voice_approval
    JarvisLiveState.Blocked -> R.string.jarvis_voice_blocked
    JarvisLiveState.EmergencyStop -> R.string.jarvis_voice_emergency
}
