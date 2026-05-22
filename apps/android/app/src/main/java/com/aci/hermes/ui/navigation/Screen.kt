package com.aci.hermes.ui.navigation

sealed class Screen(val route: String) {
    data object Splash : Screen("splash")
    data object Setup : Screen("setup")
    data object Provider : Screen("provider")
    data object Chat : Screen("chat")
    data object Status : Screen("status")
    data object Settings : Screen("settings")
    data object Diagnostics : Screen("diagnostics")
}
