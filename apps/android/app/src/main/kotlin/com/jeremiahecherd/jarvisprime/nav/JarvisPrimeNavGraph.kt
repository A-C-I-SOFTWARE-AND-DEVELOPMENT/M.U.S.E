package com.jeremiahecherd.jarvisprime.nav

import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.jeremiahecherd.jarvisprime.data.OnboardingState
import com.jeremiahecherd.jarvisprime.data.SettingsRepository
import com.jeremiahecherd.jarvisprime.ui.home.HomeScreen
import com.jeremiahecherd.jarvisprime.ui.onboarding.EmergencyStopScreen
import com.jeremiahecherd.jarvisprime.ui.onboarding.FinishScreen
import com.jeremiahecherd.jarvisprime.ui.onboarding.InteractiveIconEducationScreen
import com.jeremiahecherd.jarvisprime.ui.onboarding.ModeSelectionScreen
import com.jeremiahecherd.jarvisprime.ui.onboarding.NotificationEducationScreen
import com.jeremiahecherd.jarvisprime.ui.onboarding.OnboardingViewModel
import com.jeremiahecherd.jarvisprime.ui.onboarding.OnboardingViewModelFactory
import com.jeremiahecherd.jarvisprime.ui.onboarding.OwnerControlScreen
import com.jeremiahecherd.jarvisprime.ui.onboarding.VoiceEducationScreen
import com.jeremiahecherd.jarvisprime.ui.onboarding.WelcomeScreen
import com.jeremiahecherd.jarvisprime.ui.onboarding.WhatJarvisDoesScreen

object Routes {
    const val WELCOME = "onboarding/welcome"
    const val WHAT = "onboarding/what"
    const val OWNER = "onboarding/owner"
    const val MODE = "onboarding/mode"
    const val NOTIFICATION = "onboarding/notification"
    const val VOICE = "onboarding/voice"
    const val ICON = "onboarding/icon"
    const val EMERGENCY_STOP = "onboarding/emergency-stop"
    const val FINISH = "onboarding/finish"
    const val HOME = "home"
}

/** Ordered list of onboarding routes — used by tests and the scaffold. */
val ONBOARDING_ROUTES: List<String> = listOf(
    Routes.WELCOME,
    Routes.WHAT,
    Routes.OWNER,
    Routes.MODE,
    Routes.NOTIFICATION,
    Routes.VOICE,
    Routes.ICON,
    Routes.EMERGENCY_STOP,
    Routes.FINISH,
)

@Composable
fun JarvisPrimeNavGraph(
    settings: SettingsRepository,
    navController: NavHostController = rememberNavController(),
) {
    val viewModel: OnboardingViewModel = viewModel(factory = OnboardingViewModelFactory(settings))
    val state: OnboardingState by viewModel.state.collectAsState(initial = OnboardingState())

    val startDestination = if (state.onboardingComplete) Routes.HOME else Routes.WELCOME

    NavHost(navController = navController, startDestination = startDestination) {
        composable(Routes.WELCOME) {
            WelcomeScreen(onNext = { navController.navigate(Routes.WHAT) })
        }
        composable(Routes.WHAT) {
            WhatJarvisDoesScreen(
                onBack = { navController.popBackStack() },
                onNext = { navController.navigate(Routes.OWNER) },
            )
        }
        composable(Routes.OWNER) {
            OwnerControlScreen(
                onBack = { navController.popBackStack() },
                onNext = { navController.navigate(Routes.MODE) },
            )
        }
        composable(Routes.MODE) {
            ModeSelectionScreen(
                state = state,
                onModeSelected = viewModel::selectMode,
                onBack = { navController.popBackStack() },
                onNext = { navController.navigate(Routes.NOTIFICATION) },
            )
        }
        composable(Routes.NOTIFICATION) {
            NotificationEducationScreen(
                state = state,
                onMarkOptedIn = viewModel::recordNotificationOptIn,
                onBack = { navController.popBackStack() },
                onNext = { navController.navigate(Routes.VOICE) },
                onSkip = { navController.navigate(Routes.VOICE) },
            )
        }
        composable(Routes.VOICE) {
            VoiceEducationScreen(
                state = state,
                onMarkOptedIn = viewModel::recordVoiceOptIn,
                onBack = { navController.popBackStack() },
                onNext = { navController.navigate(Routes.ICON) },
                onSkip = { navController.navigate(Routes.ICON) },
            )
        }
        composable(Routes.ICON) {
            InteractiveIconEducationScreen(
                onBack = { navController.popBackStack() },
                onNext = { navController.navigate(Routes.EMERGENCY_STOP) },
            )
        }
        composable(Routes.EMERGENCY_STOP) {
            EmergencyStopScreen(
                onBack = { navController.popBackStack() },
                onNext = { navController.navigate(Routes.FINISH) },
            )
        }
        composable(Routes.FINISH) {
            FinishScreen(
                onFinish = {
                    viewModel.completeOnboarding()
                    navController.navigate(Routes.HOME) {
                        popUpTo(Routes.WELCOME) { inclusive = true }
                    }
                },
            )
        }
        composable(Routes.HOME) {
            HomeScreen(
                state = state,
                onToggleEmergencyStop = viewModel::toggleEmergencyStop,
                onReplayOnboarding = {
                    viewModel.replayOnboarding()
                    navController.navigate(Routes.WELCOME) {
                        popUpTo(Routes.HOME) { inclusive = true }
                    }
                },
            )
        }
    }
}
