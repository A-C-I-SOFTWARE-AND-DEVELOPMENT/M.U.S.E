package com.aci.hermes.ui.permissions

import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import com.aci.hermes.di.AppContainer
import com.aci.hermes.safety.JarvisPermission
import com.aci.hermes.safety.PermissionKernel

/**
 * Composable wrapper that handles the user-side of a permission
 * request. Callers drive it by setting [requested] non-null; the
 * router then runs the Permission Kernel decision and either shows
 * the education sheet, invokes the system dialog, or routes the user
 * to Settings when previously denied with "Don't ask again".
 *
 * The router NEVER calls the OS dialog directly — it goes through the
 * `SystemPromptLauncher` bound by the Activity into [AppContainer].
 */
@Composable
fun PermissionRouter(
    container: AppContainer,
    requested: JarvisPermission?,
    onComplete: () -> Unit,
) {
    var educationFor by remember { mutableStateOf<JarvisPermission?>(null) }

    LaunchedEffect(requested) {
        val perm = requested ?: return@LaunchedEffect
        when (val next = container.permissionKernel.requestPermission(perm)) {
            is PermissionKernel.NextStep.ShowEducation -> {
                educationFor = next.permission
            }
            is PermissionKernel.NextStep.SendToSettings -> {
                container.systemPromptLauncher()?.openAppSettings()
                onComplete()
            }
            PermissionKernel.NextStep.AlreadyGranted -> onComplete()
            is PermissionKernel.NextStep.AwaitSystemDecision -> {
                // Already inside the OS dialog — nothing more to do.
                onComplete()
            }
            is PermissionKernel.NextStep.InvokeSystemDialog -> {
                container.systemPromptLauncher()?.launch(next.permission)
                onComplete()
            }
        }
    }

    educationFor?.let { perm ->
        PermissionEducationSheet(
            permission = perm,
            onContinue = {
                val step = container.permissionKernel.acknowledgeEducation(perm)
                if (step is PermissionKernel.NextStep.InvokeSystemDialog) {
                    container.systemPromptLauncher()?.launch(step.permission)
                }
                educationFor = null
                onComplete()
            },
            onDismiss = {
                container.permissionKernel.cancelEducation(perm)
                educationFor = null
                onComplete()
            },
        )
    }
}
