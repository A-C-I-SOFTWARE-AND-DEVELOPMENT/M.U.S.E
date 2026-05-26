package com.aci.hermes.data.jarvis

enum class ResponseLength {
    CONCISE,
    BALANCED,
    DETAILED;

    val displayName: String
        get() = when (this) {
            CONCISE -> "Concise"
            BALANCED -> "Balanced"
            DETAILED -> "Detailed"
        }

    companion object {
        fun fromName(name: String?): ResponseLength =
            entries.firstOrNull { it.name == name } ?: BALANCED
    }
}
