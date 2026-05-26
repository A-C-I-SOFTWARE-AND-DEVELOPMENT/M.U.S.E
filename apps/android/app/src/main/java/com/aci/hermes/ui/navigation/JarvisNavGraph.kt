package com.aci.hermes.ui.navigation

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Assignment
import androidx.compose.material.icons.automirrored.filled.Chat
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.RuleFolder
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.stringResource
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.aci.hermes.R
import com.aci.hermes.data.model.TargetTool
import com.aci.hermes.di.AppContainer
import com.aci.hermes.ui.screens.approval.ApprovalsScreen
import com.aci.hermes.ui.screens.approval.ApprovalsViewModel
import com.aci.hermes.ui.screens.audit.AuditScreen
import com.aci.hermes.ui.screens.audit.AuditViewModel
import com.aci.hermes.ui.screens.chat.ChatScreen
import com.aci.hermes.ui.screens.chat.ChatViewModel
import com.aci.hermes.ui.screens.diagnostics.DiagnosticsScreen
import com.aci.hermes.ui.screens.diagnostics.DiagnosticsViewModel
import com.aci.hermes.ui.screens.emergency.EmergencyStopScreen
import com.aci.hermes.ui.screens.emergency.EmergencyStopViewModel
import com.aci.hermes.ui.screens.gateway.GatewayScreen
import com.aci.hermes.ui.screens.gateway.GatewayViewModel
import com.aci.hermes.ui.screens.home.HomeScreen
import com.aci.hermes.ui.screens.home.HomeViewModel
import com.aci.hermes.ui.screens.memory.MemoryScreen
import com.aci.hermes.ui.screens.memory.MemoryViewModel
import com.aci.hermes.ui.screens.notifications.NotificationsScreen
import com.aci.hermes.ui.screens.notifications.NotificationsViewModel
import com.aci.hermes.ui.screens.onboarding.OnboardingScreen
import com.aci.hermes.ui.screens.onboarding.OnboardingViewModel
import com.aci.hermes.ui.screens.orchestrator.OrchestratorScreen
import com.aci.hermes.ui.screens.orchestrator.OrchestratorViewModel
import com.aci.hermes.ui.screens.orchestrator.TaskDetailScreen
import com.aci.hermes.ui.screens.orchestrator.TaskDetailViewModel
import com.aci.hermes.ui.screens.settings.SettingsScreen
import com.aci.hermes.ui.screens.settings.SettingsViewModel
import com.aci.hermes.ui.screens.skills.SkillsScreen
import com.aci.hermes.ui.screens.skills.SkillsViewModel
import com.aci.hermes.ui.screens.social.SocialScreen
import com.aci.hermes.ui.screens.social.SocialViewModel
import com.aci.hermes.ui.screens.splash.SplashScreen
import com.aci.hermes.ui.screens.voice.VoiceCaptureScreen
import com.aci.hermes.ui.screens.voice.VoiceCaptureViewModel

/** Bottom-nav entries. Keep tight — five items max so the bar fits one-handed. */
internal data class BottomNavItem(
    val screen: Screen,
    val icon: ImageVector,
    val labelRes: Int,
)

internal val BottomNavItems = listOf(
    BottomNavItem(Screen.Home, Icons.Default.Home, R.string.nav_home),
    BottomNavItem(Screen.Chat, Icons.AutoMirrored.Filled.Chat, R.string.nav_chat),
    BottomNavItem(Screen.Approvals, Icons.Default.RuleFolder, R.string.nav_approvals),
    BottomNavItem(Screen.Tasks, Icons.AutoMirrored.Filled.Assignment, R.string.nav_tasks),
    BottomNavItem(Screen.Audit, Icons.Default.History, R.string.nav_audit),
)

@Composable
fun JarvisNavHost(container: AppContainer) {
    val nav = rememberNavController()
    val onboarded by container.settingsRepository.hasOnboarded.collectAsState(initial = true)

    val start = if (onboarded) Screen.Splash.route else Screen.Onboarding.route

    NavHost(navController = nav, startDestination = start) {

        composable(Screen.Splash.route) {
            SplashScreen(onReady = {
                nav.navigate(Screen.Home.route) {
                    popUpTo(Screen.Splash.route) { inclusive = true }
                }
            })
        }

        composable(Screen.Onboarding.route) {
            val vm: OnboardingViewModel = viewModel(factory = remember { container.onboardingVmFactory() })
            OnboardingScreen(
                viewModel = vm,
                onFinished = {
                    nav.navigate(Screen.Home.route) {
                        popUpTo(Screen.Onboarding.route) { inclusive = true }
                    }
                },
            )
        }

        composable(Screen.Home.route) {
            val vm: HomeViewModel = viewModel(factory = remember { container.homeVmFactory() })
            JarvisScaffold(nav = nav, current = Screen.Home) {
                HomeScreen(
                    viewModel = vm,
                    onOpenChat = { nav.navigate(Screen.Chat.route) },
                    onOpenVoice = { nav.navigate(Screen.Voice.route) },
                    onOpenTasks = { nav.navigate(Screen.Tasks.route) },
                    onOpenApprovals = { nav.navigate(Screen.Approvals.route) },
                    onOpenAudit = { nav.navigate(Screen.Audit.route) },
                    onOpenMemory = { nav.navigate(Screen.Memory.route) },
                    onOpenSocial = { nav.navigate(Screen.Social.route) },
                    onOpenGateway = { nav.navigate(Screen.Gateway.route) },
                    onOpenNotifications = { nav.navigate(Screen.Notifications.route) },
                    onOpenSkills = { nav.navigate(Screen.Skills.route) },
                    onOpenEmergencyStop = { nav.navigate(Screen.EmergencyStop.route) },
                    onOpenSettings = { nav.navigate(Screen.Settings.route) },
                )
            }
        }

        composable(Screen.Chat.route) {
            val vm: ChatViewModel = viewModel(factory = remember { container.chatVmFactory() })
            JarvisScaffold(nav = nav, current = Screen.Chat) {
                ChatScreen(
                    viewModel = vm,
                    onOpenVoice = { nav.navigate(Screen.Voice.route) },
                    onSuggestionNavigate = { dest -> nav.navigate(dest) },
                )
            }
        }

        composable(Screen.Approvals.route) {
            val vm: ApprovalsViewModel = viewModel(factory = remember { container.approvalsVmFactory() })
            JarvisScaffold(nav = nav, current = Screen.Approvals) {
                ApprovalsScreen(viewModel = vm)
            }
        }

        composable(Screen.Tasks.route) {
            val vm: OrchestratorViewModel = viewModel(factory = remember { container.orchestratorVmFactory() })
            JarvisScaffold(nav = nav, current = Screen.Tasks) {
                OrchestratorScreen(
                    viewModel = vm,
                    onOpenTask = { taskId ->
                        nav.navigate(
                            if (taskId == null) Screen.TaskDetail.forNew()
                            else Screen.TaskDetail.forTask(taskId)
                        )
                    },
                    onPrepareHandoff = { target ->
                        nav.navigate(Screen.TaskDetail.forNew(target.name))
                    },
                    onOpenSettings = { nav.navigate(Screen.Settings.route) },
                    onOpenDiagnostics = { nav.navigate(Screen.Diagnostics.route) },
                )
            }
        }

        composable(Screen.Audit.route) {
            val vm: AuditViewModel = viewModel(factory = remember { container.auditVmFactory() })
            JarvisScaffold(nav = nav, current = Screen.Audit) {
                AuditScreen(viewModel = vm)
            }
        }

        // Secondary destinations (no bottom-nav highlight)
        composable(Screen.Memory.route) {
            val vm: MemoryViewModel = viewModel(factory = remember { container.memoryVmFactory() })
            JarvisScaffold(nav = nav, current = null) {
                MemoryScreen(viewModel = vm, onBack = { nav.popBackStack() })
            }
        }

        composable(Screen.Social.route) {
            val vm: SocialViewModel = viewModel(factory = remember { container.socialVmFactory() })
            JarvisScaffold(nav = nav, current = null) {
                SocialScreen(viewModel = vm, onBack = { nav.popBackStack() })
            }
        }

        composable(Screen.Gateway.route) {
            val vm: GatewayViewModel = viewModel(factory = remember { container.gatewayVmFactory() })
            JarvisScaffold(nav = nav, current = null) {
                GatewayScreen(viewModel = vm, onBack = { nav.popBackStack() })
            }
        }

        composable(Screen.Notifications.route) {
            val vm: NotificationsViewModel = viewModel(factory = remember { container.notificationsVmFactory() })
            JarvisScaffold(nav = nav, current = null) {
                NotificationsScreen(
                    viewModel = vm,
                    onBack = { nav.popBackStack() },
                    onOpenApprovals = {
                        nav.navigate(Screen.Approvals.route) {
                            popUpTo(Screen.Home.route)
                        }
                    },
                )
            }
        }

        composable(Screen.Skills.route) {
            val vm: SkillsViewModel = viewModel(factory = remember { container.skillsVmFactory() })
            JarvisScaffold(nav = nav, current = null) {
                SkillsScreen(viewModel = vm, onBack = { nav.popBackStack() })
            }
        }

        composable(Screen.EmergencyStop.route) {
            val vm: EmergencyStopViewModel = viewModel(factory = remember { container.emergencyVmFactory() })
            JarvisScaffold(nav = nav, current = null) {
                EmergencyStopScreen(viewModel = vm, onBack = { nav.popBackStack() })
            }
        }

        composable(Screen.Voice.route) {
            val vm: VoiceCaptureViewModel = viewModel(factory = remember { container.voiceVmFactory() })
            JarvisScaffold(nav = nav, current = null) {
                VoiceCaptureScreen(viewModel = vm, onBack = { nav.popBackStack() })
            }
        }

        composable(Screen.Settings.route) {
            val vm: SettingsViewModel = viewModel(factory = remember { container.settingsVmFactory() })
            JarvisScaffold(nav = nav, current = null) {
                SettingsScreen(
                    viewModel = vm,
                    onBack = { nav.popBackStack() },
                    onOpenDiagnostics = { nav.navigate(Screen.Diagnostics.route) },
                )
            }
        }

        composable(Screen.Diagnostics.route) {
            val vm: DiagnosticsViewModel = viewModel(factory = remember { container.diagnosticsVmFactory() })
            JarvisScaffold(nav = nav, current = null) {
                DiagnosticsScreen(viewModel = vm, onBack = { nav.popBackStack() })
            }
        }

        // Legacy alias — keep so any external deep link to "orchestrator"
        // still lands somewhere sensible.
        composable(Screen.Orchestrator.route) {
            val vm: OrchestratorViewModel = viewModel(factory = remember { container.orchestratorVmFactory() })
            JarvisScaffold(nav = nav, current = Screen.Tasks) {
                OrchestratorScreen(
                    viewModel = vm,
                    onOpenTask = { taskId ->
                        nav.navigate(
                            if (taskId == null) Screen.TaskDetail.forNew()
                            else Screen.TaskDetail.forTask(taskId)
                        )
                    },
                    onPrepareHandoff = { target ->
                        nav.navigate(Screen.TaskDetail.forNew(target.name))
                    },
                    onOpenSettings = { nav.navigate(Screen.Settings.route) },
                    onOpenDiagnostics = { nav.navigate(Screen.Diagnostics.route) },
                )
            }
        }

        composable(
            route = Screen.TaskDetail.route,
            arguments = listOf(
                navArgument(Screen.TaskDetail.ARG_TASK_ID) {
                    type = NavType.StringType
                    nullable = false
                    defaultValue = "new"
                },
                navArgument(Screen.TaskDetail.ARG_TARGET) {
                    type = NavType.StringType
                    nullable = true
                    defaultValue = null
                },
            ),
        ) { entry ->
            val rawId = entry.arguments?.getString(Screen.TaskDetail.ARG_TASK_ID)
            val taskId = rawId?.takeIf { it.isNotBlank() && it != "new" }
            val targetName = entry.arguments?.getString(Screen.TaskDetail.ARG_TARGET)
            val target = targetName?.let { runCatching { TargetTool.valueOf(it) }.getOrNull() }
            val vm: TaskDetailViewModel = viewModel(
                factory = remember(taskId, targetName) {
                    container.taskDetailVmFactory(taskId, target)
                },
            )
            TaskDetailScreen(viewModel = vm, onBack = { nav.popBackStack() })
        }
    }
}

/**
 * Shared scaffold that places the bottom nav under every primary
 * screen. Secondary destinations (settings, voice, etc.) pass [current]
 * = null so no item is highlighted.
 */
@Composable
internal fun JarvisScaffold(
    nav: NavHostController,
    current: Screen?,
    content: @Composable (Modifier) -> Unit,
) {
    androidx.compose.material3.Scaffold(
        bottomBar = { JarvisBottomBar(nav = nav, current = current) },
    ) { padding ->
        Box(modifier = Modifier.fillMaxSize().padding(padding)) {
            content(Modifier)
        }
    }
}

@Composable
internal fun JarvisBottomBar(nav: NavHostController, current: Screen?) {
    val backStackEntry by nav.currentBackStackEntryAsState()
    val currentRoute = backStackEntry?.destination?.route ?: current?.route
    NavigationBar {
        BottomNavItems.forEach { item ->
            val selected = currentRoute == item.screen.route
            NavigationBarItem(
                selected = selected,
                onClick = {
                    if (!selected) {
                        nav.navigate(item.screen.route) {
                            popUpTo(nav.graph.findStartDestination().id) { saveState = true }
                            launchSingleTop = true
                            restoreState = true
                        }
                    }
                },
                icon = { Icon(item.icon, contentDescription = null) },
                label = { Text(stringResource(item.labelRes)) },
            )
        }
    }
}
