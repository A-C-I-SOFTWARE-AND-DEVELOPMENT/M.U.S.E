package com.aci.hermes.ui.navigation

/**
 * MUSE navigation routes.
 *
 * The Android module keeps the legacy `com.aci.hermes` package name and a few
 * internal class names (HermesService, AppContainer, HermesNavHost) where
 * technical compatibility requires it, but every route, screen title, and
 * user-facing label is MUSE.
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
    /** Mobile-native cockpit for every backend job (JobQueue + orchestrator). */
    data object Jobs : Screen("jobs")
    /** Legacy clipboard-handoff flow — preserved, reached from Home quick links. */
    data object Tasks : Screen("tasks")
    data object Approvals : Screen("approvals")
    data object Memory : Screen("memory")
    data object Evidence : Screen("evidence")
    data object Audit : Screen("audit")
    data object Capability : Screen("capability")
    data object Control : Screen("control")

    // Full-screen pushes.
    data object Settings : Screen("settings")
    data object Diagnostics : Screen("diagnostics")
    data object ModelRoute : Screen("model_route")

    /** Local model (Gemma / Ollama) honest status + smoke test. */
    data object ModelCenter : Screen("model_center")

    /** Release / download / signing / backend facts (honest, no fake CI state). */
    data object ReleaseCenter : Screen("release_center")

    /** Device-control consent + action log; pushed from the Control tab. */
    data object DeviceControl : Screen("device_control")

    /** Owner-gated device pairing (code → token); pushed from Settings. */
    data object Pairing : Screen("pairing")

    data object AuditDetail : Screen("audit_detail/{auditId}") {
        const val ARG_AUDIT_ID = "auditId"
        fun forAudit(id: String): String = "audit_detail/$id"
    }

    /** Activity timeline over the orchestrator event ledger (full-screen push). */
    data object LedgerTimeline : Screen("ledger")

    data object LedgerEventDetail : Screen("ledger_event/{eventId}") {
        const val ARG_EVENT_ID = "eventId"

        /** [eventId] is `"<jobId>:<index>"`; URL-encode the `:` for the route. */
        fun forEvent(eventId: String): String =
            "ledger_event/" + java.net.URLEncoder.encode(eventId, "UTF-8")
    }

    data object TaskDetail : Screen("task_detail/{taskId}?target={target}") {
        const val ARG_TASK_ID = "taskId"
        const val ARG_TARGET = "target"
        fun forTask(id: String): String = "task_detail/$id"
        fun forNew(target: String? = null): String =
            if (target == null) "task_detail/new" else "task_detail/new?target=$target"
    }
    /** GraphRAG knowledge-graph browser; full-screen push (deep-linked from
     *  Home + Settings, not a bottom-nav tab). */
    data object Knowledge : Screen("knowledge")

    /** WebView host for the gateway's Neural Observatory page; full-screen
     *  push (deep-linked from Settings beside Knowledge, not a shell tab). */
    data object Observatory : Screen("observatory")

    data object JobDetail : Screen("job_detail/{jobId}") {
        const val ARG_JOB_ID = "jobId"
        fun forJob(id: String): String = "job_detail/$id"
    }
    data object JarvisLive : Screen("jarvis_live")
    data object AvatarPicker : Screen("avatar_picker")

    /** v1.5 standalone-local coding cockpit: capture a coding task. */
    data object NewCodingTask : Screen("coding/new")

    /** The bounded work packet for one coding task (full-screen push). */
    data object WorkPacketDetail : Screen("coding/packet/{taskId}") {
        const val ARG_TASK_ID = "taskId"
        fun forTask(id: String): String = "coding/packet/$id"
    }

    /** Code Handoff Hub: queued / sent / blocked coding tasks. */
    data object CodeHandoff : Screen("coding/handoff")

    /** Hands-free voice capture; full-screen push reached from Home. */
    data object Voice : Screen("voice")

    /** Mobile-native Research Mode (Evidence Engine); full-screen push. */
    data object Research : Screen("research")

    companion object {
        // `by lazy` is deliberate: these collections dereference the `route`
        // of several `Screen` data objects. If they were eager, initializing
        // `Screen` *via one of those data objects* (e.g. `Screen.Approvals` —
        // which a notification deep-link does) would re-enter that object's
        // half-finished `<clinit>` and read a null `route` → NPE. Deferring
        // the dereference until first use makes init order-independent.

        /** Routes that render inside [JarvisShell]. */
        val shellRoutes: Set<String> by lazy {
            setOf(
                Home.route,
                Chat.route,
                Jobs.route,
                Tasks.route,
                Approvals.route,
                Memory.route,
                Evidence.route,
                Audit.route,
                Capability.route,
                Control.route,
            )
        }

        /** Bottom-nav tabs, in display order. Jobs is the primary cockpit tab;
         *  the legacy handoff Tasks list stays reachable from Home quick links.
         *  `by lazy` defers the `data object` dereferences until first use so a
         *  half-finished companion `<clinit>` can never read a null route. */
        val bottomTabs: List<BottomTab> by lazy {
            listOf(
                BottomTab(Home, BottomTab.Icon.HOME, labelKey = "nav_home"),
                BottomTab(Jobs, BottomTab.Icon.JOBS, labelKey = "nav_jobs"),
                BottomTab(Chat, BottomTab.Icon.CHAT, labelKey = "nav_chat"),
                BottomTab(Approvals, BottomTab.Icon.APPROVALS, labelKey = "nav_approvals"),
                BottomTab(Control, BottomTab.Icon.CONTROL, labelKey = "nav_control"),
            )
        }

        /**
         * Canonical list of shell destinations surfaced as Home quick-links,
         * in display order. This is the single source of truth the Home
         * screen renders from, so a shell destination can never become
         * unreachable: every [shellRoutes] entry must be covered by either a
         * [bottomTabs] tab or a quick-link here (asserted in ScreenTest).
         * (This is what made Capability deep-link-only before it was added.)
         */
        val homeQuickLinks: List<Screen> by lazy {
            listOf(
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
}

/** Lightweight descriptor for the bottom-nav row. */
data class BottomTab(
    val screen: Screen,
    val icon: Icon,
    val labelKey: String,
) {
    // `Capability` is not in the bottom-nav row by design (deep-linked from
    // Home quick links + Settings); it is a shell destination but not a tab.
    enum class Icon { HOME, TASKS, JOBS, CHAT, APPROVALS, CONTROL }
}
