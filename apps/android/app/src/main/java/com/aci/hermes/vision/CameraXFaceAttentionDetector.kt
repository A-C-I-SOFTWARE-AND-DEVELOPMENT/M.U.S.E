package com.aci.hermes.vision

import android.content.Context
import androidx.camera.core.CameraSelector
import androidx.camera.core.ExperimentalGetImage
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.core.content.ContextCompat
import androidx.lifecycle.LifecycleOwner
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.face.FaceDetection
import com.google.mlkit.vision.face.FaceDetector
import com.google.mlkit.vision.face.FaceDetectorOptions
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow

/**
 * On-device camera attention via CameraX + ML Kit face detection.
 *
 * **Privacy:** runs only while collected (the caller gates this on an
 * explicit opt-in + a visible indicator), uses the front camera, analyses
 * each frame in memory and closes it immediately, and reports **presence
 * only** — `PRESENT` when ≥1 face is in view, `ABSENT` otherwise. No frame,
 * image, identity, or expression is stored or transmitted. ML Kit runs
 * fully on-device.
 *
 * Bound to the supplied [LifecycleOwner]; the cold [Flow] also unbinds the
 * camera when the collector cancels, so the camera is released the moment
 * attention is no longer needed.
 *
 * The single `ImageProxy.getImage()` opt-in is confined to [FaceAnalyzer]
 * (which CameraX invokes internally), so callers of [attention] never have
 * to opt into `@ExperimentalGetImage`.
 */
class CameraXFaceAttentionDetector(
    context: Context,
    private val lifecycleOwner: LifecycleOwner,
) : AttentionDetector {

    private val appContext = context.applicationContext

    override fun attention(): Flow<AttentionState> = callbackFlow {
        val detector = FaceDetection.getClient(
            FaceDetectorOptions.Builder()
                .setPerformanceMode(FaceDetectorOptions.PERFORMANCE_MODE_FAST)
                .build(),
        )
        val executor = ContextCompat.getMainExecutor(appContext)
        var provider: ProcessCameraProvider? = null

        val analysis = ImageAnalysis.Builder()
            .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
            .build()
            .apply { setAnalyzer(executor, FaceAnalyzer(detector) { trySend(it) }) }

        val future = ProcessCameraProvider.getInstance(appContext)
        future.addListener({
            val cameraProvider = runCatching { future.get() }.getOrNull()
            if (cameraProvider == null) {
                close()
                return@addListener
            }
            provider = cameraProvider
            runCatching {
                cameraProvider.unbindAll()
                cameraProvider.bindToLifecycle(
                    lifecycleOwner,
                    CameraSelector.DEFAULT_FRONT_CAMERA,
                    analysis,
                )
            }.onFailure { close(it) }
        }, executor)

        awaitClose {
            executor.execute {
                runCatching { provider?.unbind(analysis) }
                analysis.clearAnalyzer()
                runCatching { detector.close() }
            }
        }
    }

    /**
     * Frame analyzer. CameraX calls [analyze] on the analysis executor; the
     * `@ExperimentalGetImage` opt-in lives here and nowhere else. The frame
     * is analysed in memory and closed immediately — never retained.
     */
    private class FaceAnalyzer(
        private val detector: FaceDetector,
        private val onState: (AttentionState) -> Unit,
    ) : ImageAnalysis.Analyzer {

        @ExperimentalGetImage
        override fun analyze(image: ImageProxy) {
            val media = image.image
            if (media == null) {
                image.close()
                return
            }
            val input = InputImage.fromMediaImage(media, image.imageInfo.rotationDegrees)
            detector.process(input)
                .addOnSuccessListener { faces ->
                    onState(if (faces.isNotEmpty()) AttentionState.PRESENT else AttentionState.ABSENT)
                }
                .addOnCompleteListener { image.close() }
        }
    }
}
