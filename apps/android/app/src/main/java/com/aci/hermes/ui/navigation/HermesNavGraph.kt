package com.aci.hermes.ui.navigation

import androidx.compose.animation.EnterTransition
import androidx.compose.animation.ExitTransition
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
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
import com.aci.hermes.ui.designsystem.museMotion
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
import com.aci.hermes.ui.screens.pairing.DevicePairingScreen
import com.aci.hermes.ui.screens.pairing.DevicePairingViewModel
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
 * Single NavHost for the entire muse app. Owns:
 *  - The pre-shell flow: Splash → (Onboarding if first run) → Home
 *  - The seven shell destinations (Home, Tasks, Chat, Approvals, Memory,
 *    Audit, Control) rendered inside [JarvisShell] with shared bottom nav
 *    and a globally-reachable Emergency Stop / Diagnostics / Settings bar.
 *  - Three full-screen pushes (Settings, Diagnostics, TaskDetail) that own
 *    their own top bar.
 *
 * The class is named HermesNavHost for compatibility with the existing
 * MainActivity entry point; everything user-visible is muse
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
        // Stand the whole agent down with one tap through the single audited
        // entry: it engages the EmergencyStopController and stops the
        // orchestrator. Device control halts as a projection of that stop
        // state (see DeviceControlController), so it tears down the overlay +
        // voice loop and drops gestures without a separate, divergent call.
        container.emergencyStop()
    }
    val openSettings: () -> Unit = { nav.navigate(Screen.Settings.route) }
    val openDiagnostics: () -> Unit = { nav.navigate(Screen.Diagnostics.route) }
    val openDeviceControl: () -> Unit = { nav.navigate(Screen.DeviceControl.route) }
    val openModelRoutes: () -> Unit = { nav.navigate(Screen.ModelRoute.route) }
    val openModelCenter: () -> Unit = { nav.navigate(Screen.ModelCenter.route) }
    val openReleaseCenter: () -> Unit = { nav.navigate(Screen.ReleaseCenter.route) }
    val openNewCodingTask: () -> Unit = { nav.navigate(Screen.NewCodingTask.route) }
    val openCodeHandoff: () -> Unit = { nav.navigate(Screen.CodeHandoff.route) }
    val openWorkPacket: (taskId: String) -> Unit = { id ->
        nav.navigate(Screen.WorkPacketDetail.forTask(id))
    }
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

    NavHost(
        navController = nav,
        startDestination = Screen.Splash.route,
        // muse motion (museMotion tweens only — no springs; the core blazes,
        // it does not wobble):
        //  * Top-level swaps (bottom tabs, pre-shell flow, the Den) fade
        //    through — incoming on the standard curve, outgoing fast.
        //  * Detail/push destinations (TaskDetail, JobDetail, ModelCenter, …)
        //    arrive with intent — emphasized fade plus a short upward settle —
        //    and pop with the exact mirror.
        enterTransition = {
            if (targetState.destination.route.isTopLevelRoute()) fadeThroughEnter() else pushEnter()
        },
        exitTransition = {
            // The outgoing surface always cedes the frame quickly.
            fadeOut(animationSpec = museMotion.fast())
        },
        popEnterTransition = {
            fadeIn(animationSpec = museMotion.standard())
        },
        popExitTransition = {
            if (initialState.destination.route.isTopLevelRoute()) {
                fadeOut(animationSpec = museMotion.fast())
            } else {
                pushPopExit()
            }
        },
    ) {
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
            openNewCodingTask = openNewCodingTask,
            openCodeHandoff = openCodeHandoff,
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
                onOpenObservatory = { nav.navigate(Screen.Observatory.route) },
                onOpenModelCenter = openModelCenter,
                onOpenReleaseCenter = openReleaseCenter,
                onOpenPairing = { nav.navigate(Screen.Pairing.route) },
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

        composable(Screen.Pairing.route) {
            val vm: DevicePairingViewModel = viewModel(
                factory = remember { container.devicePairingVmFactory() },
            )
            DevicePairingScreen(viewModel = vm, onBack = { nav.popBackStack() })
        }
        composable(Screen.ModelRoute.route) {
            val vm: ModelRouteViewModel = viewModel(factory = remember { container.modelRouteVmFactory() })
            ModelRouteScreen(viewModel = vm, onBack = { nav.popBackStack() })
        }

        composable(Screen.ModelCenter.route) {
            val vm: com.aci.hermes.ui.screens.model.ModelCenterViewModel =
                viewModel(factory = remember { container.modelCenterVmFactory() })
            com.aci.hermes.ui.screens.model.ModelCenterScreen(
                viewModel = vm,
                onBack = { nav.popBackStack() },
            )
        }

        composable(Screen.ReleaseCenter.route) {
            val vm: com.aci.hermes.ui.screens.releasecenter.ReleaseCenterViewModel =
                viewModel(factory = remember { container.releaseCenterVmFactory() })
            com.aci.hermes.ui.screens.releasecenter.ReleaseCenterScreen(
                viewModel = vm,
                onBack = { nav.popBackStack() },
            )
        }

        composable(Screen.AvatarPicker.route) {
            val vm: AvatarPickerViewModel = viewModel(factory = remember { container.avatarPickerVmFactory() })
            AvatarPickerScreen(viewModel = vm, onBack = { nav.popBackStack() })
        }

        // ── v1.5 standalone-local coding cockpit ────────────────────────
        composable(Screen.NewCodingTask.route) {
            val vm: com.aci.hermes.ui.screens.coding.NewCodingTaskViewModel =
                viewModel(factory = remember { container.newCodingTaskVmFactory() })
            com.aci.hermes.ui.screens.coding.NewCodingTaskScreen(
                viewModel = vm,
                onBack = { nav.popBackStack() },
                onOpenPacket = { id ->
                    // Replace New with the packet so Back returns to the caller.
                    nav.navigate(Screen.WorkPacketDetail.forTask(id)) {
                        popUpTo(Screen.NewCodingTask.route) { inclusive = true }
                    }
                },
            )
        }

        composable(
            route = Screen.WorkPacketDetail.route,
            arguments = listOf(
                navArgument(Screen.WorkPacketDetail.ARG_TASK_ID) {
                    type = NavType.StringType
                    nullable = false
                },
            ),
        ) { entry ->
            val taskId = entry.arguments?.getString(Screen.WorkPacketDetail.ARG_TASK_ID).orEmpty()
            val vm: com.aci.hermes.ui.screens.coding.WorkPacketDetailViewModel =
                viewModel(factory = remember(taskId) { container.workPacketVmFactory(taskId) })
            com.aci.hermes.ui.screens.coding.WorkPacketDetailScreen(
                viewModel = vm,
                onBack = { nav.popBackStack() },
            )
        }

        composable(Screen.CodeHandoff.route) {
            val vm: com.aci.hermes.ui.screens.coding.CodeHandoffHubViewModel =
                viewModel(factory = remember { container.codeHandoffVmFactory() })
            com.aci.hermes.ui.screens.coding.CodeHandoffHubScreen(
                viewModel = vm,
                onBack = { nav.popBackStack() },
                onOpenPacket = openWorkPacket,
                onNewTask = openNewCodingTask,
            )
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

        composable(Screen.Observatory.route) {
            // WebView host for the gateway's Neural Observatory page. It is a
            // thin frame around remote content, so it reads the connection
            // facts straight from the same stores the cockpit client uses
            // (gatewayEndpoint + encrypted cockpitToken) — no ViewModel, no
            // parallel settings store.
            com.aci.hermes.ui.screens.observatory.ObservatoryScreen(
                settingsRepository = container.settingsRepository,
                cockpitClient = container.cockpitClient,
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
    openNewCodingTask: () -> Unit,
    openCodeHandoff: () -> Unit,
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
                    openNewCodingTask = openNewCodingTask,
                    openCodeHandoff = openCodeHandoff,
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

/**
 * Routes that swap as peers — the shell destinations (bottom tabs +
 * quick-link siblings), the pre-shell flow (Splash, Onboarding), and the
 * Den ([Screen.JarvisLive], which acts as a home, not a detail push).
 */
private fun String?.isTopLevelRoute(): Boolean =
    this != null && (
        this in Screen.shellRoutes ||
            this == Screen.Splash.route ||
            this == Screen.Onboarding.route ||
            this == Screen.JarvisLive.route
        )

/** Fade-through arrival for top-level swaps: incoming on the standard curve. */
private fun fadeThroughEnter(): EnterTransition =
    fadeIn(animationSpec = museMotion.standard())

/** Detail/push arrival: emphasized fade + a short upward settle (1/24 height). */
private fun pushEnter(): EnterTransition =
    fadeIn(animationSpec = museMotion.emphasized()) +
        slideInVertically(animationSpec = museMotion.emphasized()) { it / 24 }

/** Exact mirror of [pushEnter], for popping a detail screen off the stack. */
private fun pushPopExit(): ExitTransition =
    fadeOut(animationSpec = museMotion.emphasized()) +
        slideOutVertically(animationSpec = museMotion.emphasized()) { it / 24 }

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

