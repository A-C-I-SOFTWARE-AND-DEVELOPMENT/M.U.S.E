package com.aci.hermes.ui.screens.live

import com.aci.hermes.data.avatar.AvatarRenderKind

/**
 * Decides which renderer a given device + profile can actually drive.
 * The decision is pure (takes plain numbers, not a Context) so the
 * fallback ladder — Character3D → Rive → AnimatedPixel → Orb — is
 * unit-tested. The host reads real `ActivityManager` / `Build` values
 * and passes them in.
 */
object DeviceCapability {

    data class Profile(
        val totalRamMb: Int,
        val apiLevel: Int,
        val isLowRamDevice: Boolean,
        val reducedMotion: Boolean,
    )

    /** Min RAM for the Filament 3D path; below this we drop to Rive. */
    const val MIN_3D_RAM_MB = 3000
    const val MIN_3D_API = 24

    /**
     * Resolve the requested [AvatarKind] down to one this device can run.
     * Reduced motion always collapses to the still [AvatarKind.Orb].
     */
    fun effectiveKind(requested: AvatarKind, profile: Profile): AvatarKind {
        if (profile.reducedMotion) return AvatarKind.Orb
        return when (requested) {
            AvatarKind.Character3D -> if (supports3D(profile)) AvatarKind.Character3D else AvatarKind.Rive
            else -> requested
        }
    }

    fun supports3D(profile: Profile): Boolean =
        !profile.isLowRamDevice &&
            profile.totalRamMb >= MIN_3D_RAM_MB &&
            profile.apiLevel >= MIN_3D_API

    /** Map the persisted render kind to the live UI kind. */
    fun kindFor(renderKind: AvatarRenderKind): AvatarKind = when (renderKind) {
        AvatarRenderKind.STILL -> AvatarKind.Pixel
        AvatarRenderKind.ANIMATED_PIXEL -> AvatarKind.AnimatedPixel
        AvatarRenderKind.RIVE -> AvatarKind.Rive
        AvatarRenderKind.CHARACTER_3D -> AvatarKind.Character3D
    }
}
