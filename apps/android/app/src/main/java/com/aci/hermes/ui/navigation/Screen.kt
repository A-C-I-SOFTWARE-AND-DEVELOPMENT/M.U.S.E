package com.aci.hermes.ui.navigation

import com.aci.hermes.data.preferences.ConnectionMode

sealed class Screen(val route: String) {
    data object Splash : Screen("splash")
    data object Setup : Screen("setup")

    /**
     * Provider editor. Optional `mode` query lets the Setup screen open the
     * editor pre-selected to Direct vs Hermes without overwriting whatever
     * the user previously saved.
     */
    data object Provider : Screen("provider?mode={mode}") {
        const val ARG_MODE = "mode"
        fun route(initialMode: ConnectionMode? = null): String =
            if (initialMode == null) "provider" else "provider?mode=${initialMode.name}"
    }

    data object Chat : Screen("chat")
    data object Status : Screen("status")
    data object Settings : Screen("settings")
    data object Diagnostics : Screen("diagnostics")
}
