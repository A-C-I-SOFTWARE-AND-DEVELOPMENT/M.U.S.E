package com.aci.hermes.ui.navigation

import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.aci.hermes.di.AppContainer
import kotlinx.coroutines.launch
import com.aci.hermes.ui.screens.chat.ChatScreen
import com.aci.hermes.ui.screens.chat.ChatViewModel
import com.aci.hermes.ui.screens.diagnostics.DiagnosticsScreen
import com.aci.hermes.ui.screens.diagnostics.DiagnosticsViewModel
import com.aci.hermes.ui.screens.provider.ProviderScreen
import com.aci.hermes.ui.screens.provider.ProviderViewModel
import com.aci.hermes.ui.screens.settings.SettingsScreen
import com.aci.hermes.ui.screens.settings.SettingsViewModel
import com.aci.hermes.ui.screens.setup.SetupScreen
import com.aci.hermes.ui.screens.splash.SplashScreen
import com.aci.hermes.ui.screens.status.StatusScreen
import com.aci.hermes.ui.screens.status.StatusViewModel

@Composable
fun HermesNavHost(container: AppContainer) {
    val nav = rememberNavController()
    val scope = rememberCoroutineScope()
    val hasOnboarded by container.settingsRepository.hasOnboarded.collectAsState(initial = null)

    // Default to Setup until the Flow emits — that way the splash never
    // loops back into itself if hasOnboarded is still null when the delay
    // elapses. Once the real value arrives, the lambda passed to Splash is
    // updated via rememberUpdatedState.
    val startDestination = if (hasOnboarded == true) Screen.Chat.route else Screen.Setup.route

    NavHost(navController = nav, startDestination = Screen.Splash.route) {
        composable(Screen.Splash.route) {
            SplashScreen(
                onReady = {
                    nav.navigate(startDestination) {
                        popUpTo(Screen.Splash.route) { inclusive = true }
                    }
                }
            )
        }
        composable(Screen.Setup.route) {
            SetupScreen(
                onContinue = { nav.navigate(Screen.Provider.route) },
                onSkip = {
                    scope.launch {
                        container.settingsRepository.setConnectionMode(
                            com.aci.hermes.data.preferences.ConnectionMode.MOCK
                        )
                        container.settingsRepository.setOnboarded(true)
                        nav.navigate(Screen.Chat.route) {
                            popUpTo(Screen.Setup.route) { inclusive = true }
                        }
                    }
                }
            )
        }
        composable(Screen.Provider.route) {
            val vm: ProviderViewModel = viewModel(factory = remember { container.providerVmFactory() })
            ProviderScreen(
                viewModel = vm,
                onSaved = {
                    nav.navigate(Screen.Chat.route) {
                        popUpTo(Screen.Setup.route) { inclusive = true }
                    }
                }
            )
        }
        composable(Screen.Chat.route) {
            val vm: ChatViewModel = viewModel(factory = remember { container.chatVmFactory() })
            ChatScreen(
                viewModel = vm,
                onOpenStatus = { nav.navigate(Screen.Status.route) },
                onOpenSettings = { nav.navigate(Screen.Settings.route) },
                onOpenDiagnostics = { nav.navigate(Screen.Diagnostics.route) }
            )
        }
        composable(Screen.Status.route) {
            val vm: StatusViewModel = viewModel(factory = remember { container.statusVmFactory() })
            StatusScreen(viewModel = vm, onBack = { nav.popBackStack() })
        }
        composable(Screen.Settings.route) {
            val vm: SettingsViewModel = viewModel(factory = remember { container.settingsVmFactory() })
            SettingsScreen(
                viewModel = vm,
                onBack = { nav.popBackStack() },
                onEditConnection = { nav.navigate(Screen.Provider.route) },
                onOpenDiagnostics = { nav.navigate(Screen.Diagnostics.route) }
            )
        }
        composable(Screen.Diagnostics.route) {
            val vm: DiagnosticsViewModel = viewModel(factory = remember { container.diagnosticsVmFactory() })
            DiagnosticsScreen(viewModel = vm, onBack = { nav.popBackStack() })
        }
    }
}
