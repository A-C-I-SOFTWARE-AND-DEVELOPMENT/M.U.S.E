package com.aci.hermes.data.jarvis

/**
 * Severity rendered before an owner-controlled change. The label is
 * shown verbatim in the confirmation dialog, so screens never roll
 * their own copy.
 */
enum class WarningLevel {
    NONE,
    NOTICE,
    SERIOUS,
    CRITICAL;

    val label: String
        get() = when (this) {
            NONE -> ""
            NOTICE -> "Heads up"
            SERIOUS -> "This is a serious change"
            CRITICAL -> "Critical — safety gate"
        }
}
