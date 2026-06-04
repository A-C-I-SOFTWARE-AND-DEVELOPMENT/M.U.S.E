package com.aci.hermes.data.model

/**
 * Maps the backend's raw local-model status strings to the **honest** display
 * vocabulary (see apps/android/docs/GEMMA_LOCAL_MODE.md). Pure — unit-tested on
 * the JVM. The cardinal rule: a model is only "Smoke-tested" after an explicit
 * smoke run succeeded *this session*; the backend GET never asserts it, so the
 * cockpit never shows readiness without evidence.
 */
object LocalModelLabels {

    fun runtime(status: String): String = when (status) {
        "runtime_reachable" -> "Runtime reachable"
        "configured" -> "Configured"
        else -> "Not configured"
    }

    /**
     * Per-model label. [smokeTested] (a successful in-session smoke) and
     * [smokeFailed] (a failed one) take precedence over the backend's
     * promotion/installed status, since they are stronger evidence.
     */
    fun model(status: String, smokeTested: Boolean, smokeFailed: Boolean = false): String = when {
        smokeFailed -> "Blocked / error"
        smokeTested -> "Smoke-tested"
        status == "promoted_for_task" -> "Promoted for task"
        status == "fallback_only" -> "Fallback only"
        else -> "Variant installed"
    }
}
