package com.aci.hermes.ui.navigation

sealed class Screen(val route: String) {
    data object Splash : Screen("splash")
    data object Onboarding : Screen("onboarding")
    data object Home : Screen("home")
    data object Chat : Screen("chat")
    data object Voice : Screen("voice")
    data object Tasks : Screen("tasks")
    data object Approvals : Screen("approvals")
    data object Memory : Screen("memory")
    data object Social : Screen("social")
    data object Audit : Screen("audit")

    data object ApprovalDetail : Screen("approval_detail/{approvalId}") {
        const val ARG_APPROVAL_ID = "approvalId"
        fun route(id: String): String = "approval_detail/$id"
    }

    data object AuditDetail : Screen("audit_detail/{auditId}") {
        const val ARG_AUDIT_ID = "auditId"
        fun route(id: String): String = "audit_detail/$id"
    }

    data object TaskDetail : Screen("task_detail/{taskId}?target={target}") {
        const val ARG_TASK_ID = "taskId"
        const val ARG_TARGET = "target"
        fun forTask(id: String): String = "task_detail/$id"
        fun forNew(target: String? = null): String =
            if (target == null) "task_detail/new" else "task_detail/new?target=$target"
    }

    data object Settings : Screen("settings")
    data object Diagnostics : Screen("diagnostics")

    companion object {
        /**
         * Stable list of every route the navigation graph registers.
         * The navigation test asserts against this set so future
         * additions are intentional.
         */
        val allRoutes: List<String> = listOf(
            Splash.route,
            Onboarding.route,
            Home.route,
            Chat.route,
            Voice.route,
            Tasks.route,
            Approvals.route,
            Memory.route,
            Social.route,
            Audit.route,
            ApprovalDetail.route,
            AuditDetail.route,
            TaskDetail.route,
            Settings.route,
            Diagnostics.route,
        )
    }
}
