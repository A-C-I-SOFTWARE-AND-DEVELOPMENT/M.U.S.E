package com.aci.hermes.ui.screens.live

import android.view.Choreographer
import android.view.SurfaceView
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.viewinterop.AndroidView
import com.google.android.filament.utils.ModelViewer
import com.google.android.filament.utils.Utils

/**
 * The high-end 3D body: a glTF/glb character rendered with Google
 * Filament. Used only when [DeviceCapability.supports3D] is true; the
 * [LivingAvatarHost] otherwise falls back to Rive or the pixel sprite,
 * so low-end phones never pay the cost.
 *
 * Like the Rive renderer it is driven by [AvatarInputs]: the model's
 * named animation clips are addressed by [AvatarPose] name, and a
 * crossfade blends between the current and target clip so locomotion
 * (run → push → settle) reads continuously rather than snapping.
 *
 * The glb ships with one animation per [AvatarPose]; finished art only
 * needs to keep those clip names. See `docs/avatar/rive-state-contract.md`
 * (the same pose contract applies to the 3D clips).
 */
@Composable
fun JarvisFilamentAvatar(
    inputs: AvatarInputs,
    glbAssetPath: String,
    contentDescription: String,
    modifier: Modifier = Modifier,
) {
    val choreographer = remember { Choreographer.getInstance() }

    AndroidView(
        modifier = modifier.semantics { this.contentDescription = contentDescription },
        factory = { context ->
            Utils.init()
            val surface = SurfaceView(context)
            val viewer = ModelViewer(surface)
            context.assets.open(glbAssetPath).use { input ->
                val bytes = input.readBytes()
                viewer.loadModelGlb(java.nio.ByteBuffer.allocateDirect(bytes.size).apply {
                    put(bytes); rewind()
                })
                viewer.transformToUnitCube()
            }
            surface.tag = FilamentHandle(viewer, glbAssetPath)
            surface
        },
        update = { surface ->
            (surface.tag as? FilamentHandle)?.applyPose(inputs)
        },
    )

    DisposableEffect(Unit) {
        val frameCallback = object : Choreographer.FrameCallback {
            override fun doFrame(frameTimeNanos: Long) {
                choreographer.postFrameCallback(this)
            }
        }
        choreographer.postFrameCallback(frameCallback)
        onDispose { choreographer.removeFrameCallback(frameCallback) }
    }
}

/**
 * Holds the live [ModelViewer] and maps an [AvatarInputs] onto the
 * model's animator. Kept tiny and out of the composable so the pose
 * → clip mapping stays readable.
 */
private class FilamentHandle(
    val viewer: ModelViewer,
    val glbAssetPath: String,
) {
    private var currentPose: AvatarPose? = null

    fun applyPose(inputs: AvatarInputs) {
        val animator = viewer.animator ?: return
        if (inputs.pose == currentPose) return
        currentPose = inputs.pose
        val clipIndex = clipIndexFor(animator, inputs.pose)
        if (clipIndex >= 0) {
            animator.applyAnimation(clipIndex, 0f)
            animator.updateBoneMatrices()
        }
    }

    private fun clipIndexFor(
        animator: com.google.android.filament.gltfio.Animator,
        pose: AvatarPose,
    ): Int {
        val name = pose.name.lowercase()
        for (i in 0 until animator.animationCount) {
            if (animator.getAnimationName(i).lowercase() == name) return i
        }
        return if (animator.animationCount > 0) 0 else -1
    }
}
