package com.aci.hermes.ui.navigation

sealed class Screen(val route: String) {
    data object Splash : Screen("splash")
    data object Orchestrator : Screen("orchestrator")
    data object TaskDetail : Screen("task_detail/{taskId}?target={target}") {
        const val ARG_TASK_ID = "taskId"
        const val ARG_TARGET = "target"
        fun forTask(id: String): String = "task_detail/$id"
        fun forNew(target: String? = null): String =
            if (target == null) "task_detail/new" else "task_detail/new?target=$target"
    }
    data object Settings : Screen("settings")
    data object Diagnostics : Screen("diagnostics")
    data object Memory : Screen("memory")
    data object MemoryDetail : Screen("memory_detail/{patternId}") {
        const val ARG_PATTERN_ID = "patternId"
        fun forPattern(id: String): String = "memory_detail/$id"
    }
}
