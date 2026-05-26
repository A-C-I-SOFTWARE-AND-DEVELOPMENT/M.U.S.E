package com.aci.hermes.ui.navigation

import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.aci.hermes.data.model.TargetTool
import com.aci.hermes.data.preferences.SettingsRepository
import com.aci.hermes.di.AppContainer
import com.aci.hermes.ui.screens.approvals.ApprovalDetailScreen
import com.aci.hermes.ui.screens.approvals.ApprovalDetailViewModel
import com.aci.hermes.ui.screens.approvals.ApprovalsScreen
import com.aci.hermes.ui.screens.approvals.ApprovalsViewModel
import com.aci.hermes.ui.screens.audit.AuditDetailScreen
import com.aci.hermes.ui.screens.audit.AuditDetailViewModel
import com.aci.hermes.ui.screens.audit.AuditScreen
import com.aci.hermes.ui.screens.audit.AuditViewModel
import com.aci.hermes.ui.screens.chat.ChatScreen
import com.aci.hermes.ui.screens.chat.ChatViewModel
import com.aci.hermes.ui.screens.diagnostics.DiagnosticsScreen
import com.aci.hermes.ui.screens.diagnostics.DiagnosticsViewModel
import com.aci.hermes.ui.screens.home.HomeScreen
import com.aci.hermes.ui.screens.home.HomeViewModel
import com.aci.hermes.ui.screens.memory.MemoryScreen
import com.aci.hermes.ui.screens.memory.MemoryViewModel
import com.aci.hermes.ui.screens.onboarding.OnboardingScreen
import com.aci.hermes.ui.screens.orchestrator.OrchestratorScreen
import com.aci.hermes.ui.screens.orchestrator.OrchestratorViewModel
import com.aci.hermes.ui.screens.orchestrator.TaskDetailScreen
import com.aci.hermes.ui.screens.orchestrator.TaskDetailViewModel
import com.aci.hermes.ui.screens.settings.SettingsScreen
import com.aci.hermes.ui.screens.settings.SettingsViewModel
import com.aci.hermes.ui.screens.social.SocialIntelligenceScreen
import com.aci.hermes.ui.screens.social.SocialIntelligenceViewModel
import com.aci.hermes.ui.screens.splash.SplashScreen
import com.aci.hermes.ui.screens.voice.VoiceCaptureScreen
import com.aci.hermes.ui.screens.voice.VoiceCaptureViewModel
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

private val onboardingScope = CoroutineScope(Dispatchers.IO + SupervisorJob())

@Composable
fun HermesNavHost(
    container: AppContainer,
    onRequestNotificationPermission: () -> Unit = {},
) {
    val nav: NavHostController = rememberNavController()

    NavHost(navController = nav, startDestination = Screen.Splash.route) {
        composable(Screen.Splash.route) {
            val hasOnboarded by container.settingsRepository.hasOnboarded.collectAsState(initial = true)
            SplashScreen(
                onReady = {
                    val next = if (!hasOnboarded) Screen.Onboarding.route
                    else Screen.Home.route
                    nav.navigate(next) {
                        popUpTo(Screen.Splash.route) { inclusive = true }
                    }
                }
            )
        }
        composable(Screen.Onboarding.route) {
            OnboardingScreen(
                onFinish = {
                    completeOnboarding(container.settingsRepository)
                    nav.navigate(Screen.Home.route) {
                        popUpTo(Screen.Onboarding.route) { inclusive = true }
                    }
                },
                onSkip = {
                    completeOnboarding(container.settingsRepository)
                    nav.navigate(Screen.Home.route) {
                        popUpTo(Screen.Onboarding.route) { inclusive = true }
                    }
                },
            )
        }
        composable(Screen.Home.route) {
            val vm: HomeViewModel = viewModel(factory = remember { container.homeVmFactory() })
            HomeScreen(
                viewModel = vm,
                onOpenChat = { nav.navigate(Screen.Chat.route) },
                onOpenVoice = { nav.navigate(Screen.Voice.route) },
                onOpenTasks = { nav.navigate(Screen.Tasks.route) },
                onOpenApprovals = { nav.navigate(Screen.Approvals.route) },
                onOpenMemory = { nav.navigate(Screen.Memory.route) },
                onOpenSocial = { nav.navigate(Screen.Social.route) },
                onOpenAudit = { nav.navigate(Screen.Audit.route) },
                onOpenDiagnostics = { nav.navigate(Screen.Diagnostics.route) },
                onOpenSettings = { nav.navigate(Screen.Settings.route) },
                onRequestNotificationPermission = onRequestNotificationPermission,
            )
        }
        composable(Screen.Chat.route) {
            val vm: ChatViewModel = viewModel(factory = remember { container.chatVmFactory() })
            ChatScreen(
                viewModel = vm,
                onBack = { nav.popBackStack() },
                onOpenVoice = { nav.navigate(Screen.Voice.route) },
                onOpenApproval = { id -> nav.navigate(Screen.ApprovalDetail.route(id)) },
            )
        }
        composable(Screen.Voice.route) {
            val vm: VoiceCaptureViewModel = viewModel(factory = remember { container.voiceVmFactory() })
            VoiceCaptureScreen(
                viewModel = vm,
                onBack = { nav.popBackStack() },
                onTaskCreated = { _ ->
                    nav.navigate(Screen.Tasks.route) {
                        popUpTo(Screen.Home.route)
                    }
                },
            )
        }
        composable(Screen.Tasks.route) {
            val vm: OrchestratorViewModel = viewModel(factory = remember { container.orchestratorVmFactory() })
            OrchestratorScreen(
                viewModel = vm,
                onOpenTask = { taskId ->
                    nav.navigate(
                        if (taskId == null) Screen.TaskDetail.forNew()
                        else Screen.TaskDetail.forTask(taskId)
                    )
                },
                onPrepareHandoff = { target -> nav.navigate(Screen.TaskDetail.forNew(target.name)) },
                onOpenSettings = { nav.navigate(Screen.Settings.route) },
                onOpenDiagnostics = { nav.navigate(Screen.Diagnostics.route) },
            )
        }
        composable(Screen.Approvals.route) {
            val vm: ApprovalsViewModel = viewModel(factory = remember { container.approvalsVmFactory() })
            ApprovalsScreen(
                viewModel = vm,
                onBack = { nav.popBackStack() },
                onOpenDetail = { id -> nav.navigate(Screen.ApprovalDetail.route(id)) },
            )
        }
        composable(
            route = Screen.ApprovalDetail.route,
            arguments = listOf(
                navArgument(Screen.ApprovalDetail.ARG_APPROVAL_ID) {
                    type = NavType.StringType
                    nullable = false
                },
            ),
        ) { entry ->
            val id = entry.arguments?.getString(Screen.ApprovalDetail.ARG_APPROVAL_ID).orEmpty()
            val vm: ApprovalDetailViewModel = viewModel(
                factory = remember(id) { container.approvalDetailVmFactory(id) },
            )
            ApprovalDetailScreen(viewModel = vm, onBack = { nav.popBackStack() })
        }
        composable(Screen.Memory.route) {
            val vm: MemoryViewModel = viewModel(factory = remember { container.memoryVmFactory() })
            MemoryScreen(viewModel = vm, onBack = { nav.popBackStack() })
        }
        composable(Screen.Social.route) {
            val vm: SocialIntelligenceViewModel = viewModel(factory = remember { container.socialVmFactory() })
            SocialIntelligenceScreen(viewModel = vm, onBack = { nav.popBackStack() })
        }
        composable(Screen.Audit.route) {
            val vm: AuditViewModel = viewModel(factory = remember { container.auditVmFactory() })
            AuditScreen(
                viewModel = vm,
                onBack = { nav.popBackStack() },
                onOpenDetail = { id -> nav.navigate(Screen.AuditDetail.route(id)) },
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
            val id = entry.arguments?.getString(Screen.AuditDetail.ARG_AUDIT_ID).orEmpty()
            val vm: AuditDetailViewModel = viewModel(
                factory = remember(id) { container.auditDetailVmFactory(id) },
            )
            AuditDetailScreen(viewModel = vm, onBack = { nav.popBackStack() })
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
        composable(Screen.Settings.route) {
            val vm: SettingsViewModel = viewModel(factory = remember { container.settingsVmFactory() })
            SettingsScreen(
                viewModel = vm,
                onBack = { nav.popBackStack() },
                onOpenDiagnostics = { nav.navigate(Screen.Diagnostics.route) },
                onRequestNotificationPermission = onRequestNotificationPermission,
            )
        }
        composable(Screen.Diagnostics.route) {
            val vm: DiagnosticsViewModel = viewModel(factory = remember { container.diagnosticsVmFactory() })
            DiagnosticsScreen(viewModel = vm, onBack = { nav.popBackStack() })
        }
    }
}

private fun completeOnboarding(settings: SettingsRepository) {
    // Fire-and-forget persistence — the screen has already navigated;
    // the persisted value catches up to the in-memory hop. Lives on a
    // single application-scoped supervisor so we don't lose the write
    // if the suspending edit yields.
    onboardingScope.launch { settings.setOnboarded(true) }
}
