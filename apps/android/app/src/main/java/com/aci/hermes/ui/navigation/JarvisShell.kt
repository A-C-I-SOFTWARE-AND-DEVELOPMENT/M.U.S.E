package com.aci.hermes.ui.navigation

import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.size
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Assignment
import androidx.compose.material.icons.automirrored.filled.Chat
import androidx.compose.material.icons.automirrored.filled.ListAlt
import androidx.compose.material.icons.filled.AdminPanelSettings
import androidx.compose.material.icons.filled.BugReport
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.PowerSettingsNew
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.aci.hermes.R
import com.aci.hermes.ui.components.rememberJarvisHaptics
import com.aci.hermes.ui.theme.JarvisInkAbyss
import com.aci.hermes.ui.theme.JarvisInkNight
import com.aci.hermes.ui.screens.live.AvatarInputs
import com.aci.hermes.ui.screens.live.AvatarKind
import com.aci.hermes.ui.screens.live.AvatarPose
import com.aci.hermes.ui.screens.live.LivingAvatarHost

/**
 * Outer chrome for the seven main destinations in the muse app
 * (Home, Tasks, Chat, Approvals, Memory, Audit, Control).
 *
 * Provides:
 *  - A consistent top app bar with the current screen title plus three
 *    globally-reachable actions: Emergency Stop, Diagnostics, Settings.
 *  - A bottom navigation row across the five primary tabs.
 *  - A confirmation dialog for the emergency stop so a stray tap can't
 *    silently kill the orchestrator service.
 *
 * Settings, Diagnostics, TaskDetail, Splash, and Onboarding own their own
 * Scaffolds and are not wrapped by this shell.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun JarvisShell(
    currentRoute: String,
    title: String,
    onNavigateTab: (Screen) -> Unit,
    onOpenSettings: () -> Unit,
    onOpenDiagnostics: () -> Unit,
    onEmergencyStop: () -> Unit,
    content: @Composable (PaddingValues) -> Unit,
) {
    var confirmStop by remember { mutableStateOf(false) }
    val haptics = rememberJarvisHaptics()

    // Pinned bar: it never collapses, but its container animates from the
    // void (JarvisInkAbyss) to the first ink step (JarvisInkNight) once
    // content scrolls beneath it — elevation by value, not shadow.
    val scrollBehavior = TopAppBarDefaults.pinnedScrollBehavior()

    Scaffold(
        modifier = Modifier.nestedScroll(scrollBehavior.nestedScrollConnection),
        topBar = {
            TopAppBar(
                title = { Text(title) },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = JarvisInkAbyss,
                    scrolledContainerColor = JarvisInkNight,
                    titleContentColor = MaterialTheme.colorScheme.primary,
                ),
                scrollBehavior = scrollBehavior,
                navigationIcon = {
                    // A persistent, breathing JARVIS presence on every screen —
                    // the "always here" parent. Tap to open the full live avatar.
                    val homeTab = Screen.bottomTabs.firstOrNull()?.screen
                    IconButton(
                        onClick = { homeTab?.let(onNavigateTab) },
                        enabled = homeTab != null,
                    ) {
                        LivingAvatarHost(
                            kind = AvatarKind.Orb,
                            inputs = AvatarInputs(
                                pose = AvatarPose.IDLE,
                                energy = 0.35f,
                                motionEnabled = true,
                            ),
                            contentDescription = stringResource(R.string.app_name),
                            modifier = Modifier.size(32.dp),
                        )
                    }
                },
                actions = {
                    IconButton(onClick = {
                        // Light acknowledgement on opening the confirm dialog;
                        // the destructive haptic belongs to the confirm itself.
                        haptics.tick()
                        confirmStop = true
                    }) {
                        Icon(
                            imageVector = Icons.Filled.PowerSettingsNew,
                            contentDescription = stringResource(R.string.nav_emergency_stop),
                            tint = MaterialTheme.colorScheme.error,
                        )
                    }
                    IconButton(onClick = onOpenDiagnostics) {
                        Icon(
                            imageVector = Icons.Filled.BugReport,
                            contentDescription = stringResource(R.string.nav_diagnostics),
                        )
                    }
                    IconButton(onClick = onOpenSettings) {
                        Icon(
                            imageVector = Icons.Filled.Settings,
                            contentDescription = stringResource(R.string.nav_settings),
                        )
                    }
                },
            )
        },
        bottomBar = {
            // Flat first ink step — no M3 tonal-elevation wash on the rail.
            NavigationBar(
                containerColor = JarvisInkNight,
                tonalElevation = 0.dp,
            ) {
                Screen.bottomTabs.forEach { tab ->
                    val selected = tab.screen.route == currentRoute
                    NavigationBarItem(
                        selected = selected,
                        onClick = {
                            if (!selected) {
                                haptics.tick()
                                onNavigateTab(tab.screen)
                            }
                        },
                        icon = { Icon(tab.icon.toVector(), contentDescription = null) },
                        label = { Text(stringResource(tab.labelKey.toLabelRes())) },
                    )
                }
            }
        },
    ) { padding ->
        content(padding)
    }

    if (confirmStop) {
        AlertDialog(
            onDismissRequest = { confirmStop = false },
            icon = {
                Icon(
                    imageVector = Icons.Filled.PowerSettingsNew,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.error,
                )
            },
            title = { Text(stringResource(R.string.emergency_stop_title)) },
            text = { Text(stringResource(R.string.emergency_stop_body)) },
            confirmButton = {
                TextButton(onClick = {
                    confirmStop = false
                    onEmergencyStop()
                }) { Text(stringResource(R.string.emergency_stop_confirm)) }
            },
            dismissButton = {
                TextButton(onClick = { confirmStop = false }) {
                    Text(stringResource(R.string.action_cancel))
                }
            },
        )
    }
}

private fun BottomTab.Icon.toVector(): ImageVector = when (this) {
    BottomTab.Icon.HOME -> Icons.Filled.Home
    BottomTab.Icon.TASKS -> Icons.AutoMirrored.Filled.Assignment
    BottomTab.Icon.JOBS -> Icons.AutoMirrored.Filled.ListAlt
    BottomTab.Icon.CHAT -> Icons.AutoMirrored.Filled.Chat
    BottomTab.Icon.APPROVALS -> Icons.Filled.CheckCircle
    BottomTab.Icon.CONTROL -> Icons.Filled.AdminPanelSettings
}

private fun String.toLabelRes(): Int = when (this) {
    "nav_home" -> R.string.nav_home
    "nav_tasks" -> R.string.nav_tasks
    "nav_jobs" -> R.string.nav_jobs
    "nav_chat" -> R.string.nav_chat
    "nav_approvals" -> R.string.nav_approvals
    "nav_control" -> R.string.nav_control
    else -> R.string.app_name
}
