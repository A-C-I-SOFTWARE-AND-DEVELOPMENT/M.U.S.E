package com.aci.hermes.safety

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update

/**
 * Jarvis Prime Permission Kernel.
 *
 * Single decision point for every Android runtime permission Jarvis
 * Prime ever asks for. The Activity / Compose layer never calls
 * `ActivityResultLauncher.launch(...)` directly — it routes through
 * [requestPermission] so the kernel can enforce the Phase 1 rules:
 *
 *   * No first-launch permission dialog.
 *   * Notification permission only after education / user action.
 *   * Microphone permission only after the user taps Voice.
 *   * No always-listening anywhere.
 *
 * The kernel is platform-agnostic — it holds state and decides the
 * next step. The Android-specific actor (Activity) implements
 * [SystemPromptLauncher] to bridge to `ActivityResultContracts`.
 */
class PermissionKernel(
    initialStates: Map<JarvisPermission, PermissionState> = emptyMap(),
) {
    private val _states: MutableStateFlow<Map<JarvisPermission, PermissionState>> =
        MutableStateFlow(JarvisPermission.entries.associateWith {
            initialStates[it] ?: PermissionState.NOT_REQUESTED
        })

    val states: StateFlow<Map<JarvisPermission, PermissionState>> = _states.asStateFlow()

    fun stateOf(permission: JarvisPermission): PermissionState =
        _states.value.getValue(permission)

    /**
     * Entry point. Always returns the next-step the caller should
     * surface in the UI. Never invokes the system dialog on its own.
     */
    fun requestPermission(permission: JarvisPermission): NextStep {
        val current = stateOf(permission)
        return when (current) {
            PermissionState.GRANTED -> NextStep.AlreadyGranted
            PermissionState.PERMANENTLY_DENIED -> NextStep.SendToSettings(permission)
            PermissionState.NOT_REQUESTED,
            PermissionState.DENIED -> {
                transition(permission, PermissionState.EDUCATION_PENDING)
                NextStep.ShowEducation(permission)
            }
            PermissionState.EDUCATION_PENDING -> NextStep.ShowEducation(permission)
            PermissionState.SYSTEM_PROMPT_PENDING -> NextStep.AwaitSystemDecision(permission)
        }
    }

    /**
     * Called when the user taps Continue in the education sheet. Moves
     * the kernel into SYSTEM_PROMPT_PENDING so the Activity is allowed
     * to launch the OS dialog.
     */
    fun acknowledgeEducation(permission: JarvisPermission): NextStep {
        require(stateOf(permission) == PermissionState.EDUCATION_PENDING) {
            "acknowledgeEducation called for ${permission.name} but state is ${stateOf(permission)}"
        }
        transition(permission, PermissionState.SYSTEM_PROMPT_PENDING)
        return NextStep.InvokeSystemDialog(permission)
    }

    /** Called when the user dismisses the education sheet without continuing. */
    fun cancelEducation(permission: JarvisPermission) {
        if (stateOf(permission) == PermissionState.EDUCATION_PENDING) {
            transition(permission, PermissionState.NOT_REQUESTED)
        }
    }

    /**
     * Called from the ActivityResultContracts callback once the OS
     * dialog returns. `permanentlyDenied` should reflect the result of
     * `shouldShowRequestPermissionRationale` on a fresh denial: if the
     * permission was denied AND the rationale is no longer shown, the
     * user picked "Don't ask again".
     */
    fun recordSystemDecision(
        permission: JarvisPermission,
        granted: Boolean,
        permanentlyDenied: Boolean = false,
    ) {
        val next = when {
            granted -> PermissionState.GRANTED
            permanentlyDenied -> PermissionState.PERMANENTLY_DENIED
            else -> PermissionState.DENIED
        }
        transition(permission, next)
    }

    /**
     * Reconcile state with the live OS at process start. Call from the
     * Activity / Application using `ContextCompat.checkSelfPermission`.
     * The reconcile only upgrades to GRANTED; it never resets a denied
     * state to NOT_REQUESTED.
     */
    fun reconcileFromSystem(permission: JarvisPermission, isCurrentlyGranted: Boolean) {
        val current = stateOf(permission)
        if (isCurrentlyGranted && current != PermissionState.GRANTED) {
            transition(permission, PermissionState.GRANTED)
        } else if (!isCurrentlyGranted && current == PermissionState.GRANTED) {
            transition(permission, PermissionState.DENIED)
        }
    }

    private fun transition(permission: JarvisPermission, to: PermissionState) {
        _states.update { map -> map.toMutableMap().also { it[permission] = to } }
    }

    /**
     * What the kernel tells the UI to do next. The UI layer pattern
     * matches on this — there is no other API surface for permissions.
     */
    sealed interface NextStep {
        data object AlreadyGranted : NextStep
        data class ShowEducation(val permission: JarvisPermission) : NextStep
        data class InvokeSystemDialog(val permission: JarvisPermission) : NextStep
        data class AwaitSystemDecision(val permission: JarvisPermission) : NextStep
        data class SendToSettings(val permission: JarvisPermission) : NextStep
    }

    /** Android-side bridge. Implemented by the Activity. */
    interface SystemPromptLauncher {
        fun launch(permission: JarvisPermission)
        fun openAppSettings()
    }
}
