package com.aci.hermes.ui.navigation

import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.aci.hermes.data.model.TargetTool
import com.aci.hermes.di.AppContainer
import com.aci.hermes.ui.screens.diagnostics.DiagnosticsScreen
import com.aci.hermes.ui.screens.diagnostics.DiagnosticsViewModel
import com.aci.hermes.ui.screens.emergency.EmergencyStopScreen
import com.aci.hermes.ui.screens.emergency.EmergencyStopViewModel
import com.aci.hermes.ui.screens.orchestrator.OrchestratorScreen
import com.aci.hermes.ui.screens.orchestrator.OrchestratorViewModel
import com.aci.hermes.ui.screens.orchestrator.TaskDetailScreen
import com.aci.hermes.ui.screens.orchestrator.TaskDetailViewModel
import com.aci.hermes.ui.screens.settings.SettingsScreen
import com.aci.hermes.ui.screens.settings.SettingsViewModel
import com.aci.hermes.ui.screens.splash.SplashScreen

@Composable
fun HermesNavHost(container: AppContainer) {
    val nav = rememberNavController()

    NavHost(navController = nav, startDestination = Screen.Splash.route) {
        composable(Screen.Splash.route) {
            SplashScreen(
                onReady = {
                    nav.navigate(Screen.Orchestrator.route) {
                        popUpTo(Screen.Splash.route) { inclusive = true }
                    }
                }
            )
        }
        composable(Screen.Orchestrator.route) {
            val vm: OrchestratorViewModel = viewModel(factory = remember { container.orchestratorVmFactory() })
            // Long-press path goes through the same controller so the
            // navigation layer doesn't need to know about state.
            val emergencyVm: EmergencyStopViewModel = viewModel(
                factory = remember { container.emergencyStopVmFactory() },
                key = "emergency_vm_orchestrator",
            )
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
                onOpenEmergencyControl = { nav.navigate(Screen.Control.route(false)) },
                onEngageEmergencyStop = { nav.navigate(Screen.Control.route(true)) },
                onLongPressEscalate = { emergencyVm.longPressEscalate() },
            )
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
            )
        }
        composable(Screen.Diagnostics.route) {
            val vm: DiagnosticsViewModel = viewModel(factory = remember { container.diagnosticsVmFactory() })
            DiagnosticsScreen(viewModel = vm, onBack = { nav.popBackStack() })
        }
        composable(
            route = Screen.Control.route,
            arguments = listOf(
                navArgument(Screen.Control.ARG_ENGAGE) {
                    type = NavType.StringType
                    nullable = true
                    defaultValue = "false"
                },
            ),
        ) { entry ->
            val engage = entry.arguments?.getString(Screen.Control.ARG_ENGAGE)?.toBoolean() == true
            val vm: EmergencyStopViewModel = viewModel(
                factory = remember { container.emergencyStopVmFactory() },
                key = "emergency_vm_control",
            )
            androidx.compose.runtime.LaunchedEffect(engage) {
                if (engage) vm.openConfirmDialog()
            }
            EmergencyStopScreen(viewModel = vm, onBack = { nav.popBackStack() })
        }
    }
}
