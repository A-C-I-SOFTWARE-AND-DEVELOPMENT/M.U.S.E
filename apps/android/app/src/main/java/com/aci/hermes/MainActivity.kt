package com.aci.hermes

import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Bundle
import android.provider.Settings
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.core.content.ContextCompat
import com.aci.hermes.data.preferences.ThemeMode
import com.aci.hermes.safety.JarvisPermission
import com.aci.hermes.safety.PermissionKernel
import com.aci.hermes.ui.navigation.HermesNavHost
import com.aci.hermes.ui.theme.HermesTheme

/**
 * Jarvis Prime entry activity.
 *
 * Deliberately quiet on first launch:
 *
 *   * No foreground service is started here. The user starts the
 *     gateway from the dashboard so they understand what the persistent
 *     notification represents.
 *   * No runtime permission dialog is opened here. Permission requests
 *     flow through [PermissionKernel] and only fire after the user has
 *     read the education sheet and tapped Continue.
 */
class MainActivity : ComponentActivity() {

    private val permissionLauncher =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
            val pending = pendingPermission ?: return@registerForActivityResult
            val permanentlyDenied = !granted && !shouldShowRequestPermissionRationale(pending.manifestName)
            kernel().recordSystemDecision(pending, granted, permanentlyDenied)
            pendingPermission = null
        }

    private var pendingPermission: JarvisPermission? = null

    private val systemPromptLauncher = object : PermissionKernel.SystemPromptLauncher {
        override fun launch(permission: JarvisPermission) {
            pendingPermission = permission
            permissionLauncher.launch(permission.manifestName)
        }

        override fun openAppSettings() {
            val intent = Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS).apply {
                data = Uri.fromParts("package", packageName, null)
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            startActivity(intent)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        val container = (application as HermesApplication).container
        container.bindActivityPromptLauncher(systemPromptLauncher)
        reconcilePermissions(container.permissionKernel)

        setContent {
            val themePref by container.settingsRepository.themeMode.collectAsState(
                initial = ThemeMode.SYSTEM
            )
            HermesTheme(themeMode = themePref) {
                HermesNavHost(container = container)
            }
        }
    }

    override fun onResume() {
        super.onResume()
        // Re-reconcile in case the user changed permissions in system
        // Settings while the app was backgrounded.
        reconcilePermissions((application as HermesApplication).container.permissionKernel)
    }

    override fun onDestroy() {
        (application as HermesApplication).container.unbindActivityPromptLauncher(systemPromptLauncher)
        super.onDestroy()
    }

    private fun kernel(): PermissionKernel =
        (application as HermesApplication).container.permissionKernel

    private fun reconcilePermissions(kernel: PermissionKernel) {
        for (perm in JarvisPermission.entries) {
            val granted = ContextCompat.checkSelfPermission(this, perm.manifestName) ==
                PackageManager.PERMISSION_GRANTED
            kernel.reconcileFromSystem(perm, granted)
        }
    }
}
