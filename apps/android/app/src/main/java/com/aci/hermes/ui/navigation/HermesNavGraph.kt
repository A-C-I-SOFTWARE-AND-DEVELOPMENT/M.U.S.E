package com.aci.hermes.ui.navigation

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
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
import com.aci.hermes.learning.state.LearningViewModel
import com.aci.hermes.data.model.TargetTool
import com.aci.hermes.di.AppContainer
import com.aci.hermes.service.JobNotifier
import com.aci.hermes.ui.screens.avatar.AvatarPickerScreen
import com.aci.hermes.ui.screens.avatar.AvatarPickerViewModel
import com.aci.hermes.ui.screens.audit.AuditDetailScreen
import com.aci.hermes.ui.screens.audit.AuditDetailViewModel
import com.aci.hermes.ui.screens.audit.AuditScreen
import com.aci.hermes.ui.screens.audit.AuditViewModel
import com.aci.hermes.ui.screens.ledger.LedgerEventDetailScreen
import com.aci.hermes.ui.screens.ledger.LedgerEventDetailViewModel
import com.aci.hermes.ui.screens.ledger.LedgerTimelineScreen
import com.aci.hermes.ui.screens.ledger.LedgerTimelineViewModel
import com.aci.hermes.ui.screens.capability.CapabilityScreen
import com.aci.hermes.ui.screens.capability.CapabilityViewModel
import com.aci.hermes.ui.screens.chat.JarvisChatScreen
import com.aci.hermes.ui.screens.chat.JarvisChatViewModel
import com.aci.hermes.ui.screens.control.ControlScreen
import com.aci.hermes.ui.screens.devicecontrol.DeviceControlScreen
import com.aci.hermes.ui.screens.devicecontrol.DeviceControlViewModel
import com.aci.hermes.ui.screens.control.ControlViewModel
import com.aci.hermes.ui.screens.diagnostics.DiagnosticsScreen
import com.aci.hermes.ui.screens.diagnostics.DiagnosticsViewModel
import com.aci.hermes.ui.screens.evidence.EvidenceScreen
import com.aci.hermes.ui.screens.evidence.EvidenceViewModel
import com.aci.hermes.ui.screens.home.HomeScreen
import com.aci.hermes.ui.screens.jobs.CockpitJobsViewModel
import com.aci.hermes.ui.screens.jobs.JobsScreen
import com.aci.hermes.ui.screens.jobs.JobsViewModel
import com.aci.hermes.ui.screens.home.JarvisHomeNavigation
import com.aci.hermes.ui.screens.home.JarvisPrimeHomeScreen
import com.aci.hermes.ui.screens.home.JarvisPrimeHomeViewModel
import com.aci.hermes.ui.screens.jobs.JobDetailScreen
import com.aci.hermes.ui.screens.jobs.JobDetailViewModel
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
fun HermesNavHost(
    container: AppContainer,
    deepLink: JobNotifier.DeepLink? = null,
    onDeepLinkHandled: () -> Unit = {},
) {
    val nav = rememberNavController()
    val coroutineScope = rememberCoroutineScope()
    val hasOnboarded by container.settingsRepository.hasOnboarded.collectAsState(initial = null)

    // Honour a notification tap: open the route MainActivity published, then
    // clear it so a recomposition/rotation doesn't re-navigate.
    val pendingDeepLink by container.pendingDeepLink.collectAsState()
    LaunchedEffect(pendingDeepLink) {
        val route = pendingDeepLink ?: return@LaunchedEffect
        nav.navigate(route) { launchSingleTop = true }
        container.consumeDeepLink()
    }

    val emergencyStop: () -> Unit = {
        // Stand the whole agent down with one tap: stop the orchestrator AND
        // halt device control (drop gestures, stop the overlay + voice loop).
        container.orchestratorServiceController.emergencyStop()
        container.deviceControlController.engageEmergencyStop()
    }
    val openSettings: () -> Unit = { nav.navigate(Screen.Settings.route) }
    val openDiagnostics: () -> Unit = { nav.navigate(Screen.Diagnostics.route) }
    val openDeviceControl: () -> Unit = { nav.navigate(Screen.DeviceControl.route) }
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
    val openJob: (jobId: String) -> Unit = { jobId ->
        nav.navigate(Screen.JobDetail.forJob(jobId))
    }
    val prepareHandoff: (TargetTool) -> Unit = { target ->
        nav.navigate(Screen.TaskDetail.forNew(target.name))
    }

    // Notification deep-links: open the exact job, the Approvals queue (for a
    // job blocked on an owner gate), or Diagnostics (backend unreachable).
    LaunchedEffect(deepLink) {
        val link = deepLink ?: return@LaunchedEffect
        when (link.destination) {
            JobNotifier.DEST_DETAIL -> link.jobId?.let { nav.navigate(Screen.JobDetail.forJob(it)) }
            JobNotifier.DEST_APPROVALS -> onNavigateTab(Screen.Approvals)
            JobNotifier.DEST_DIAGNOSTICS -> nav.navigate(Screen.Diagnostics.route)
            else -> Unit
        }
        onDeepLinkHandled()
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
            openJob = openJob,
            prepareHandoff = prepareHandoff,
            openDeviceControl = openDeviceControl,
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
            TaskDetailScreen(
                viewModel = vm,
                onBack = { nav.popBackStack() },
                relatedLoader = { jobId -> container.cockpitGraphRepository.relatedForJob(jobId) },
            )
        }

        composable(
            route = Screen.JobDetail.route,
            arguments = listOf(
                navArgument(Screen.JobDetail.ARG_JOB_ID) {
                    type = NavType.StringType
                    nullable = false
                },
            ),
        ) { entry ->
            val jobId = entry.arguments?.getString(Screen.JobDetail.ARG_JOB_ID).orEmpty()
            val vm: JobDetailViewModel = viewModel(
                factory = remember(jobId) { container.jobDetailVmFactory(jobId) },
            )
            JobDetailScreen(viewModel = vm, onBack = { nav.popBackStack() })
        }

        composable(Screen.Settings.route) {
            val vm: SettingsViewModel = viewModel(factory = remember { container.settingsVmFactory() })
            SettingsScreen(
                viewModel = vm,
                onBack = { nav.popBackStack() },
                onOpenDiagnostics = openDiagnostics,
                onOpenModelRoutes = openModelRoutes,
                onOpenAvatarPicker = { nav.navigate(Screen.AvatarPicker.route) },
                onOpenKnowledge = { nav.navigate(Screen.Knowledge.route) },
            )
        }

        composable(Screen.Diagnostics.route) {
            val vm: DiagnosticsViewModel = viewModel(factory = remember { container.diagnosticsVmFactory() })
            DiagnosticsScreen(viewModel = vm, onBack = { nav.popBackStack() })
        }

        composable(Screen.DeviceControl.route) {
            val vm: DeviceControlViewModel = viewModel(
                factory = remember { container.deviceControlVmFactory() },
            )
            DeviceControlScreen(viewModel = vm, onBack = { nav.popBackStack() })
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
                // Route to the gated owner-approval queue (never auto-approve).
                onOpenApprovals = { onNavigateTab(Screen.Approvals) },
                // Swipe to the active job's detail, or the Tasks list when none.
                onOpenCurrentJob = { jobId ->
                    if (jobId == null) onNavigateTab(Screen.Tasks) else openTask(jobId)
                },
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
            AuditDetailScreen(
                viewModel = vm,
                onBack = { nav.popBackStack() },
                relatedLoader = { container.cockpitGraphRepository.relatedForEvidence(auditId) },
            )
        }

        composable(Screen.Knowledge.route) {
            val vm: com.aci.hermes.ui.screens.knowledge.KnowledgeGraphViewModel = viewModel(
                factory = remember { container.knowledgeGraphVmFactory() },
            )
            com.aci.hermes.ui.screens.knowledge.KnowledgeGraphScreen(
                viewModel = vm,
                onBack = { nav.popBackStack() },
            )
        }

        composable(Screen.LedgerTimeline.route) {
            val vm: LedgerTimelineViewModel = viewModel(
                factory = remember { container.ledgerTimelineVmFactory() },
            )
            LedgerTimelineScreen(
                viewModel = vm,
                onBack = { nav.popBackStack() },
                onOpenEvent = { eventId -> nav.navigate(Screen.LedgerEventDetail.forEvent(eventId)) },
            )
        }

        composable(
            route = Screen.LedgerEventDetail.route,
            arguments = listOf(
                navArgument(Screen.LedgerEventDetail.ARG_EVENT_ID) {
                    type = NavType.StringType
                    nullable = false
                },
            ),
        ) { entry ->
            val eventId = entry.arguments?.getString(Screen.LedgerEventDetail.ARG_EVENT_ID).orEmpty()
            val vm: LedgerEventDetailViewModel = viewModel(
                factory = remember(eventId) { container.ledgerEventVmFactory(eventId) },
            )
            LedgerEventDetailScreen(viewModel = vm, onBack = { nav.popBackStack() })
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
    openJob: (jobId: String) -> Unit,
    prepareHandoff: (TargetTool) -> Unit,
    openDeviceControl: () -> Unit,
) {
    composable(Screen.Home.route) {
        val vm: JarvisPrimeHomeViewModel = viewModel(
            factory = remember { container.jarvisPrimeHomeVmFactory() },
        )
        ShellHost(
            currentRoute = Screen.Home.route,
            titleRes = R.string.nav_home,
            onNavigateTab = onNavigateTab,
            openSettings = openSettings,
            openDiagnostics = openDiagnostics,
            emergencyStop = emergencyStop,
        ) { padding ->
            JarvisPrimeHomeScreen(
                viewModel = vm,
                paddingValues = padding,
                navigation = JarvisHomeNavigation(
                    openChat = { onNavigateTab(Screen.Chat) },
                    openVoiceCapture = { nav.navigate(Screen.Voice.route) },
                    openTasks = openTask,
                    openTasksList = { onNavigateTab(Screen.Tasks) },
                    openApprovals = { onNavigateTab(Screen.Approvals) },
                    openMemory = { onNavigateTab(Screen.Memory) },
                    openControl = { onNavigateTab(Screen.Control) },
                    openSettings = openSettings,
                    openAudit = { onNavigateTab(Screen.Audit) },
                    openDiagnostics = openDiagnostics,
                    openNewTask = { openTask(null) },
                ),
            )
        }
    }

    composable(Screen.Tasks.route) {
        val vm: OrchestratorViewModel = viewModel(
            factory = remember { container.orchestratorVmFactory() },
        )
        val jobsVm: CockpitJobsViewModel = viewModel(
            factory = remember { container.cockpitJobsVmFactory() },
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
                jobsViewModel = jobsVm,
            )
        }
    }

    composable(Screen.Jobs.route) {
        val vm: JobsViewModel = viewModel(
            factory = remember { container.jobsVmFactory() },
        )
        ShellHost(
            currentRoute = Screen.Jobs.route,
            titleRes = R.string.nav_jobs,
            onNavigateTab = onNavigateTab,
            openSettings = openSettings,
            openDiagnostics = openDiagnostics,
            emergencyStop = emergencyStop,
        ) { padding ->
            JobsScreen(viewModel = vm, paddingValues = padding, onOpenJob = openJob)
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
        val learningVm: LearningViewModel = viewModel(
            factory = remember { container.learningVmFactory() },
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
                ApprovalsScreen(
                    viewModel = vm,
                    onBack = { nav.popBackStack() },
                    learningViewModel = learningVm,
                )
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
                MemoryScreen(
                    viewModel = vm,
                    onBack = { nav.popBackStack() },
                    relatedLoader = { memoryId ->
                        container.cockpitGraphRepository.relatedForMemory(memoryId)
                    },
                )
            }
        }
    }

    composable(Screen.Evidence.route) {
        val vm: EvidenceViewModel = viewModel(
            factory = remember { container.evidenceVmFactory() },
        )
        ShellHost(
            currentRoute = Screen.Evidence.route,
            titleRes = R.string.nav_evidence,
            onNavigateTab = onNavigateTab,
            openSettings = openSettings,
            openDiagnostics = openDiagnostics,
            emergencyStop = emergencyStop,
        ) { padding ->
            Box(modifier = Modifier.padding(padding)) {
                EvidenceScreen(viewModel = vm, onBack = { nav.popBackStack() })
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
                    onOpenActivity = { nav.navigate(Screen.LedgerTimeline.route) },
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
        val controlVm: ControlViewModel = viewModel(
            factory = remember { container.controlVmFactory() },
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
                onOpenDeviceControl = openDeviceControl,
                controlViewModel = controlVm,
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

