package com.aci.hermes.ui.navigation

/**
 * Jarvis Prime navigation routes.
 *
 * The Android module keeps the legacy `com.aci.hermes` package name and a few
 * internal class names (HermesService, AppContainer, HermesNavHost) where
 * technical compatibility requires it, but every route, screen title, and
 * user-facing label is Jarvis Prime.
 *
 * Splash and Onboarding are pre-shell destinations. The main destinations
 * (Home, Chat, Tasks, Approvals, Memory, Audit, Control) are rendered inside
 * [JarvisShell] so they share bottom navigation, the global emergency stop,
 * and quick links to Settings + Diagnostics. TaskDetail, Settings, and
 * Diagnostics are full-screen pushes that own their own top bar.
 */
sealed class Screen(val route: String) {
    data object Splash : Screen("splash")
    data object Onboarding : Screen("onboarding")

    // Main shell destinations (bottom nav).
    data object Home : Screen("home")
    data object Chat : Screen("chat")
    data object Tasks : Screen("tasks")
    /** Cockpit orchestration jobs (the real JobQueue), distinct from the
     *  local-handoff [Tasks]. Backed by `CockpitJobsRepository`. */
    data object Jobs : Screen("jobs")
    data object Approvals : Screen("approvals")
    data object Memory : Screen("memory")
    data object Evidence : Screen("evidence")
    data object Audit : Screen("audit")
    data object Capability : Screen("capability")
    data object Control : Screen("control")

    // Full-screen pushes.
    data object Settings : Screen("settings")
    data object Diagnostics : Screen("diagnostics")

    /** Device-control consent + action log; pushed from the Control tab. */
    data object DeviceControl : Screen("device_control")

    data object AuditDetail : Screen("audit_detail/{auditId}") {
        const val ARG_AUDIT_ID = "auditId"
        fun forAudit(id: String): String = "audit_detail/$id"
    }

    data object TaskDetail : Screen("task_detail/{taskId}?target={target}") {
        const val ARG_TASK_ID = "taskId"
        const val ARG_TARGET = "target"
        fun forTask(id: String): String = "task_detail/$id"
        fun forNew(target: String? = null): String =
            if (target == null) "task_detail/new" else "task_detail/new?target=$target"
    }
    data object JarvisLive : Screen("jarvis_live")
    data object AvatarPicker : Screen("avatar_picker")

    /** Hands-free voice capture; full-screen push reached from Home. */
    data object Voice : Screen("voice")

    companion object {
        /** Routes that render inside [JarvisShell]. */
        val shellRoutes: Set<String> = setOf(
            Home.route,
            Chat.route,
            Tasks.route,
            Jobs.route,
            Approvals.route,
            Memory.route,
            Evidence.route,
            Audit.route,
            Capability.route,
            Control.route,
        )

        /** Bottom-nav tabs, in display order. */
        val bottomTabs: List<BottomTab> = listOf(
            BottomTab(Home, BottomTab.Icon.HOME, labelKey = "nav_home"),
            BottomTab(Tasks, BottomTab.Icon.TASKS, labelKey = "nav_tasks"),
            BottomTab(Chat, BottomTab.Icon.CHAT, labelKey = "nav_chat"),
            BottomTab(Approvals, BottomTab.Icon.APPROVALS, labelKey = "nav_approvals"),
            BottomTab(Control, BottomTab.Icon.CONTROL, labelKey = "nav_control"),
        )

        /**
         * Canonical list of shell destinations surfaced as Home quick-links,
         * in display order. This is the single source of truth the Home
         * screen renders from, so a shell destination can never become
         * unreachable: every [shellRoutes] entry must be covered by either a
         * [bottomTabs] tab or a quick-link here (asserted in ScreenTest).
         * (This is what made Capability deep-link-only before it was added.)
         */
        val homeQuickLinks: List<Screen> = listOf(
            Tasks,
            Jobs,
            Chat,
            Approvals,
            Memory,
            Audit,
            Capability,
            Evidence,
            Control,
        )
    }
}

/** Lightweight descriptor for the bottom-nav row. */
data class BottomTab(
    val screen: Screen,
    val icon: Icon,
    val labelKey: String,
) {
    // `Capability` is not in the bottom-nav row by design (deep-linked from
    // Home quick links + Settings); it is a shell destination but not a tab.
    enum class Icon { HOME, TASKS, CHAT, APPROVALS, CONTROL }
}
