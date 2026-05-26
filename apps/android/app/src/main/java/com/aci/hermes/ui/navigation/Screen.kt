package com.aci.hermes.ui.navigation

/** Screen routes. The bottom-nav exposes a curated subset (see [JarvisDestinations]). */
sealed class Screen(val route: String) {
    data object Splash : Screen("splash")
    data object Onboarding : Screen("onboarding")

    // Bottom-nav destinations
    data object Home : Screen("home")
    data object Chat : Screen("chat")
    data object Tasks : Screen("tasks")
    data object Approvals : Screen("approvals")
    data object Audit : Screen("audit")

    // Drawer / secondary destinations
    data object Memory : Screen("memory")
    data object Social : Screen("social")
    data object Gateway : Screen("gateway")
    data object Notifications : Screen("notifications")
    data object Skills : Screen("skills")
    data object EmergencyStop : Screen("emergency_stop")
    data object Voice : Screen("voice")
    data object Settings : Screen("settings")
    data object Diagnostics : Screen("diagnostics")

    /** Legacy alias for the orchestrator screen — kept for any deep links. */
    data object Orchestrator : Screen("orchestrator")

    data object TaskDetail : Screen("task_detail/{taskId}?target={target}") {
        const val ARG_TASK_ID = "taskId"
        const val ARG_TARGET = "target"
        fun forTask(id: String): String = "task_detail/$id"
        fun forNew(target: String? = null): String =
            if (target == null) "task_detail/new" else "task_detail/new?target=$target"
    }
}
