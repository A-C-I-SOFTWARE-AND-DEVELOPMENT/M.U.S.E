package com.aci.hermes.vision

import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.emptyFlow

/**
 * Whether the user is currently looking at / present in front of the
 * device, as judged on-device. Deliberately coarse — we never expose
 * identity, expression, or imagery, only presence.
 */
enum class AttentionState { PRESENT, ABSENT }

/**
 * Source of attention signals. The real implementation
 * ([CameraXFaceAttentionDetector]) uses CameraX + on-device ML Kit face
 * detection; [NoOpAttentionDetector] is the fallback when the user has not
 * opted in (or no camera is available), so the rest of the system can wire
 * to the interface unconditionally.
 *
 * Privacy contract for any real implementation:
 *  - runs **only** while the user has explicitly opted in AND a visible
 *    indicator is shown,
 *  - analyses frames in memory and never stores or transmits them,
 *  - reports presence only — never identity, expression, or images.
 */
interface AttentionDetector {
    fun attention(): Flow<AttentionState>
}

/** Emits nothing — the default until the user opts into camera attention. */
object NoOpAttentionDetector : AttentionDetector {
    override fun attention(): Flow<AttentionState> = emptyFlow()
}

/**
 * Pure decision logic for camera attention, kept Android-free so it is
 * unit-tested without a camera.
 */
object AttentionPolicy {

    /**
     * Camera attention may run only when the user has opted in, Presence
     * Mode is on, and the CAMERA permission is granted. All three are
     * required — opting in alone never starts the camera.
     */
    fun active(
        cameraAttentionEnabled: Boolean,
        presenceModeEnabled: Boolean,
        cameraPermissionGranted: Boolean,
    ): Boolean = cameraAttentionEnabled && presenceModeEnabled && cameraPermissionGranted

    /**
     * Arm listening on the rising edge of attention (ABSENT/null → PRESENT)
     * so simply remaining in view does not re-trigger every frame.
     */
    fun shouldArmOnTransition(previous: AttentionState?, current: AttentionState): Boolean =
        current == AttentionState.PRESENT && previous != AttentionState.PRESENT
}
