package com.aci.hermes.ui.navigation

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavController
import androidx.navigation.NavGraphBuilder
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.aci.hermes.R
import com.aci.hermes.approval.state.ApprovalViewModel
import com.aci.hermes.approval.ui.screens.ApprovalsScreen
import com.aci.hermes.data.model.TargetTool
import com.aci.hermes.di.AppContainer
import com.aci.hermes.ui.screens.avatar.AvatarPickerScreen
import com.aci.hermes.ui.screens.avatar.AvatarPickerViewModel
import com.aci.hermes.ui.screens.audit.AuditDetailScreen
import com.aci.hermes.ui.screens.audit.AuditDetailViewModel
import com.aci.hermes.ui.screens.audit.AuditScreen
import com.aci.hermes.ui.screens.audit.AuditViewModel
import com.aci.hermes.ui.screens.capability.CapabilityScreen
import com.aci.hermes.ui.screens.capability.CapabilityViewModel
import com.aci.hermes.ui.screens.chat.JarvisChatScreen
import com.aci.hermes.ui.screens.chat.JarvisChatViewModel
import com.aci.hermes.ui.screens.control.ControlScreen
import com.aci.hermes.ui.screens.diagnostics.DiagnosticsScreen
import com.aci.hermes.ui.screens.diagnostics.DiagnosticsViewModel
import com.aci.hermes.ui.screens.home.HomeScreen
import com.aci.hermes.ui.screens.live.JarvisLiveScreen
import com.aci.hermes.ui.screens.live.JarvisLiveViewModel
import com.aci.hermes.ui.screens.memory.MemoryScreen
import com.aci.hermes.ui.screens.memory.MemoryViewModel
import com.aci.hermes.ui.screens.modelroute.ModelRouteScreen
import com.aci.hermes.ui.screens.modelroute.ModelRouteViewModel
import com.aci.hermes.ui.screens.onboarding.OnboardingScreen
import com.aci.hermes.ui.screens.orchestrator.OrchestratorViewModel
import com.aci.hermes.ui.screens.orchestrator.TaskDetailScreen
import com.aci.hermes.ui.screens.orchestrator.TaskDetailViewModel
import com.aci.hermes.ui.screens.settings.SettingsScreen
import com.aci.hermes.ui.screens.settings.SettingsViewModel
import com.aci.hermes.ui.screens.splash.SplashScreen
import com.aci.hermes.ui.screens.tasks.TasksScreen
import com.aci.hermes.ui.screens.voice.VoiceCaptureScreen
import com.aci.hermes.ui.screens.voice.VoiceCaptureViewModel
import kotlinx.coroutines.launch

/**
 * Single NavHost for the entire Jarvis Prime app. Owns:
 *  - The pre-shell flow: Splash → (Onboarding if first run) → Home
 *  - The seven shell destinations (Home, Tasks, Chat, Approvals, Memory,
 *    Audit, Control) rendered inside [JarvisShell] with shared bottom nav
 *    and a globally-reachable Emergency Stop / Diagnostics / Settings bar.
 *  - Three full-screen pushes (Settings, Diagnostics, TaskDetail) that own
 *    their own top bar.
 *
 * The class is named HermesNavHost for compatibility with the existing
 * MainActivity entry point; everything user-visible is Jarvis Prime.
 */
@Composable
fun HermesNavHost(container: AppContainer) {
    val nav = rememberNavController()
    val coroutineScope = rememberCoroutineScope()
    val hasOnboarded by container.settingsRepository.hasOnboarded.collectAsState(initial = null)

    val emergencyStop: () -> Unit = {
        container.orchestratorServiceController.emergencyStop()
    }
    val openSettings: () -> Unit = { nav.navigate(Screen.Settings.route) }
    val openDiagnostics: () -> Unit = { nav.navigate(Screen.Diagnostics.route) }
    val openModelRoutes: () -> Unit = { nav.navigate(Screen.ModelRoute.route) }
    val onNavigateTab: (Screen) -> Unit = { screen ->
        nav.navigate(screen.route) {
            popUpTo(Screen.Home.route) { saveState = true }
            launchSingleTop = true
            restoreState = true
        }
    }
    val openTask: (taskId: String?) -> Unit = { taskId ->
        nav.navigate(
            if (taskId == null) Screen.TaskDetail.forNew()
            else Screen.TaskDetail.forTask(taskId),
        )
    }
    val prepareHandoff: (TargetTool) -> Unit = { target ->
        nav.navigate(Screen.TaskDetail.forNew(target.name))
    }

    NavHost(navController = nav, startDestination = Screen.Splash.route) {
        composable(Screen.Splash.route) {
            SplashScreen(
                onReady = {
                    // The avatar's Den is the heart of the app — land there first.
                    val next = when (hasOnboarded) {
                        true -> Screen.JarvisLive.route
                        false -> Screen.Onboarding.route
                        null -> Screen.JarvisLive.route // safe default if pref not loaded yet
                    }
                    nav.navigate(next) {
                        popUpTo(Screen.Splash.route) { inclusive = true }
                    }
                },
            )
        }

        composable(Screen.Onboarding.route) {
            OnboardingScreen(
                onFinish = {
                    coroutineScope.launch {
                        container.settingsRepository.setOnboarded(true)
                    }
                    nav.navigate(Screen.Home.route) {
                        popUpTo(Screen.Onboarding.route) { inclusive = true }
                    }
                },
            )
        }

        shellDestinations(
            nav = nav,
            container = container,
            onNavigateTab = onNavigateTab,
            openSettings = openSettings,
            openDiagnostics = openDiagnostics,
            emergencyStop = emergencyStop,
            openTask = openTask,
            prepareHandoff = prepareHandoff,
        )

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

        composable(Screen.Settings.route) {
            val vm: SettingsViewModel = viewModel(factory = remember { container.settingsVmFactory() })
            SettingsScreen(
                viewModel = vm,
                onBack = { nav.popBackStack() },
                onOpenDiagnostics = openDiagnostics,
                onOpenModelRoutes = openModelRoutes,
                onOpenAvatarPicker = { nav.navigate(Screen.AvatarPicker.route) },
            )
        }

        composable(Screen.Diagnostics.route) {
            val vm: DiagnosticsViewModel = viewModel(factory = remember { container.diagnosticsVmFactory() })
            DiagnosticsScreen(viewModel = vm, onBack = { nav.popBackStack() })
        }

        composable(Screen.ModelRoute.route) {
            val vm: ModelRouteViewModel = viewModel(factory = remember { container.modelRouteVmFactory() })
            ModelRouteScreen(viewModel = vm, onBack = { nav.popBackStack() })
        }

        composable(Screen.AvatarPicker.route) {
            val vm: AvatarPickerViewModel = viewModel(factory = remember { container.avatarPickerVmFactory() })
            AvatarPickerScreen(viewModel = vm, onBack = { nav.popBackStack() })
        }

        composable(Screen.JarvisLive.route) {
            val vm: JarvisLiveViewModel = viewModel(factory = remember { container.jarvisLiveVmFactory() })
            JarvisLiveScreen(
                viewModel = vm,
                // The Den is the home; the menu button opens the rest of the app.
                onBack = {
                    nav.navigate(Screen.Home.route) { launchSingleTop = true }
                },
                onOpenAvatarPicker = { nav.navigate(Screen.AvatarPicker.route) },
                onOpenSettings = openSettings,
            )
        }

        composable(Screen.Voice.route) {
            val vm: VoiceCaptureViewModel = viewModel(factory = remember { container.voiceCaptureVmFactory() })
            VoiceCaptureScreen(
                viewModel = vm,
                onBack = { nav.popBackStack() },
                onTaskCreated = { taskId ->
                    // Drop the capture screen, then open the new task's detail.
                    nav.popBackStack()
                    openTask(taskId)
                },
            )
        }

        composable(
            route = Screen.AuditDetail.route,
            arguments = listOf(
                navArgument(Screen.AuditDetail.ARG_AUDIT_ID) {
                    type = NavType.StringType
                    nullable = false
                },
            ),
        ) { entry ->
            val auditId = entry.arguments?.getString(Screen.AuditDetail.ARG_AUDIT_ID).orEmpty()
            val vm: AuditDetailViewModel = viewModel(
                factory = remember(auditId) { container.auditDetailVmFactory(auditId) },
            )
            AuditDetailScreen(viewModel = vm, onBack = { nav.popBackStack() })
        }
        // Approvals is registered as a shell destination (with bottom-nav + emergency
        // stop) inside `shellDestinations` below. The legacy top-level Approvals
        // composable introduced by #107 was removed during integration to avoid a
        // duplicate-route registration that would shadow the shell-wrapped version.
    }
}

private fun NavGraphBuilder.shellDestinations(
    nav: NavController,
    container: AppContainer,
    onNavigateTab: (Screen) -> Unit,
    openSettings: () -> Unit,
    openDiagnostics: () -> Unit,
    emergencyStop: () -> Unit,
    openTask: (taskId: String?) -> Unit,
    prepareHandoff: (TargetTool) -> Unit,
) {
    composable(Screen.Home.route) {
        val vm: OrchestratorViewModel = viewModel(
            factory = remember { container.orchestratorVmFactory() },
        )
        ShellHost(
            currentRoute = Screen.Home.route,
            titleRes = R.string.nav_home,
            onNavigateTab = onNavigateTab,
            openSettings = openSettings,
            openDiagnostics = openDiagnostics,
            emergencyStop = emergencyStop,
        ) { padding ->
            HomeScreen(
                viewModel = vm,
                paddingValues = padding,
                onNavigate = onNavigateTab,
                onOpenTask = openTask,
                onPrepareHandoff = prepareHandoff,
                onOpenJarvisLive = { nav.navigate(Screen.JarvisLive.route) },
                onOpenVoice = { nav.navigate(Screen.Voice.route) },
            )
        }
    }

    composable(Screen.Tasks.route) {
        val vm: OrchestratorViewModel = viewModel(
            factory = remember { container.orchestratorVmFactory() },
        )
        ShellHost(
            currentRoute = Screen.Tasks.route,
            titleRes = R.string.nav_tasks,
            onNavigateTab = onNavigateTab,
            openSettings = openSettings,
            openDiagnostics = openDiagnostics,
            emergencyStop = emergencyStop,
        ) { padding ->
            TasksScreen(
                viewModel = vm,
                paddingValues = padding,
                onOpenTask = openTask,
                onOpenApprovals = { onNavigateTab(Screen.Approvals) },
                onOpenAudit = { onNavigateTab(Screen.Audit) },
            )
        }
    }

    composable(Screen.Chat.route) {
        val vm: JarvisChatViewModel = viewModel(
            factory = remember { container.jarvisChatVmFactory() },
        )
        ShellHost(
            currentRoute = Screen.Chat.route,
            titleRes = R.string.nav_chat,
            onNavigateTab = onNavigateTab,
            openSettings = openSettings,
            openDiagnostics = openDiagnostics,
            emergencyStop = emergencyStop,
        ) { padding ->
            JarvisChatScreen(viewModel = vm, paddingValues = padding)
        }
    }

    composable(Screen.Approvals.route) {
        val vm: ApprovalViewModel = viewModel(
            factory = remember { container.approvalsVmFactory() },
        )
        ShellHost(
            currentRoute = Screen.Approvals.route,
            titleRes = R.string.nav_approvals,
            onNavigateTab = onNavigateTab,
            openSettings = openSettings,
            openDiagnostics = openDiagnostics,
            emergencyStop = emergencyStop,
        ) { padding ->
            // ApprovalsScreen owns its own internal padding; pass the shell padding
            // so the underlying surface respects bottom-nav inset.
            Box(modifier = Modifier.padding(padding)) {
                ApprovalsScreen(viewModel = vm, onBack = { nav.popBackStack() })
            }
        }
    }

    composable(Screen.Memory.route) {
        val vm: MemoryViewModel = viewModel(
            factory = remember { container.memoryVmFactory() },
        )
        ShellHost(
            currentRoute = Screen.Memory.route,
            titleRes = R.string.nav_memory,
            onNavigateTab = onNavigateTab,
            openSettings = openSettings,
            openDiagnostics = openDiagnostics,
            emergencyStop = emergencyStop,
        ) { padding ->
            Box(modifier = Modifier.padding(padding)) {
                MemoryScreen(viewModel = vm, onBack = { nav.popBackStack() })
            }
        }
    }

    composable(Screen.Audit.route) {
        val vm: AuditViewModel = viewModel(
            factory = remember { container.auditVmFactory() },
        )
        ShellHost(
            currentRoute = Screen.Audit.route,
            titleRes = R.string.nav_audit,
            onNavigateTab = onNavigateTab,
            openSettings = openSettings,
            openDiagnostics = openDiagnostics,
            emergencyStop = emergencyStop,
        ) { padding ->
            Box(modifier = Modifier.padding(padding)) {
                AuditScreen(
                    viewModel = vm,
                    onBack = { nav.popBackStack() },
                    onOpenAudit = { auditId ->
                        nav.navigate(Screen.AuditDetail.forAudit(auditId))
                    },
                )
            }
        }
    }

    composable(Screen.Capability.route) {
        val vm: CapabilityViewModel = viewModel(
            factory = remember { container.capabilityVmFactory() },
        )
        ShellHost(
            currentRoute = Screen.Capability.route,
            titleRes = R.string.nav_capability,
            onNavigateTab = onNavigateTab,
            openSettings = openSettings,
            openDiagnostics = openDiagnostics,
            emergencyStop = emergencyStop,
        ) { padding ->
            Box(modifier = Modifier.padding(padding)) {
                CapabilityScreen(viewModel = vm, onBack = { nav.popBackStack() })
            }
        }
    }

    composable(Screen.Control.route) {
        val vm: OrchestratorViewModel = viewModel(
            factory = remember { container.orchestratorVmFactory() },
        )
        ShellHost(
            currentRoute = Screen.Control.route,
            titleRes = R.string.nav_control,
            onNavigateTab = onNavigateTab,
            openSettings = openSettings,
            openDiagnostics = openDiagnostics,
            emergencyStop = emergencyStop,
        ) { padding ->
            ControlScreen(
                viewModel = vm,
                paddingValues = padding,
                onEmergencyStop = emergencyStop,
            )
        }
    }
}

@Composable
private fun ShellHost(
    currentRoute: String,
    titleRes: Int,
    onNavigateTab: (Screen) -> Unit,
    openSettings: () -> Unit,
    openDiagnostics: () -> Unit,
    emergencyStop: () -> Unit,
    content: @Composable (PaddingValues) -> Unit,
) {
    JarvisShell(
        currentRoute = currentRoute,
        title = stringResource(titleRes),
        onNavigateTab = onNavigateTab,
        onOpenSettings = openSettings,
        onOpenDiagnostics = openDiagnostics,
        onEmergencyStop = emergencyStop,
        content = content,
    )
}

