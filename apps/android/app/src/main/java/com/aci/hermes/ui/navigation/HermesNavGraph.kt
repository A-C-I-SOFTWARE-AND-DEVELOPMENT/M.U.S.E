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
import com.aci.hermes.ui.screens.jarvis_live.JarvisLiveScreen
import com.aci.hermes.ui.screens.jarvis_live.JarvisLiveViewModel
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
                    nav.navigate(Screen.JarvisLive.route) {
                        popUpTo(Screen.Splash.route) { inclusive = true }
                    }
                }
            )
        }
        composable(Screen.JarvisLive.route) {
            val vm: JarvisLiveViewModel = viewModel(
                factory = remember { container.jarvisLiveVmFactory() },
            )
            JarvisLiveScreen(
                viewModel = vm,
                onOpenSettings = { nav.navigate(Screen.Settings.route) },
            )
        }
        composable(Screen.Orchestrator.route) {
            val vm: OrchestratorViewModel = viewModel(factory = remember { container.orchestratorVmFactory() })
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
    }
}
