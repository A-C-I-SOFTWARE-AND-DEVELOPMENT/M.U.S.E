package com.aci.hermes.data.avatar

import kotlinx.serialization.Serializable

@Serializable
enum class AvatarSource { BUILTIN, GENERATED }

@Serializable
enum class JarvisBuiltin { GUARDIAN_SHIELD, FAST_WORKER_BOLT, KNOWLEDGE_MEMORY, COMMAND_AUTO }

@Serializable
enum class PixelSize(val px: Int) {
    CHUNKY_16(16),
    BALANCED_32(32),
    DETAILED_48(48),
}

@Serializable
enum class AvatarStyle { NONE, NAVY_GOLD, CYAN_GLOW, MONOCHROME_TERMINAL }

/**
 * Which renderer animates this avatar. [STILL] is the original
 * single-image behavior (pixel-art picker output). The others are the
 * "truly alive" character renderers and carry the matching asset path
 * in [AvatarProfile]. Maps 1:1 to
 * [com.aci.hermes.ui.screens.live.AvatarKind] at the UI edge.
 */
@Serializable
enum class AvatarRenderKind { STILL, ANIMATED_PIXEL, RIVE, CHARACTER_3D }

@Serializable
data class AvatarProfile(
    val source: AvatarSource,
    val builtin: JarvisBuiltin? = null,
    val generatedPath: String? = null,
    val pixelSize: PixelSize = PixelSize.BALANCED_32,
    val style: AvatarStyle = AvatarStyle.NAVY_GOLD,
    val renderKind: AvatarRenderKind = AvatarRenderKind.STILL,
    /** Sprite sheet (ANIMATED_PIXEL), .riv (RIVE), or .glb (CHARACTER_3D). */
    val animatedAssetPath: String? = null,
) {
    init {
        when (source) {
            AvatarSource.BUILTIN -> require(builtin != null && generatedPath == null) {
                "BUILTIN avatar requires builtin and no generatedPath"
            }
            AvatarSource.GENERATED -> require(generatedPath != null && builtin == null) {
                "GENERATED avatar requires generatedPath and no builtin"
            }
        }
        if (renderKind != AvatarRenderKind.STILL) {
            require(!animatedAssetPath.isNullOrBlank()) {
                "$renderKind avatar requires an animatedAssetPath"
            }
        }
    }
}
